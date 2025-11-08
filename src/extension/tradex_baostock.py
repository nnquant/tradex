"""
tradex 的 baostock MCP 扩展，覆盖A股K线、指数、估值与季频财务接口。

:mod:`tradex_baostock` 通过 baostock 官方 Python API 提供结构化工具，
方便在 Agent 环境中直接获取行情与财务指标数据。
"""

from __future__ import annotations

import datetime as dt
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

import baostock as bs
import pandas as pd
from claude_agent_sdk import create_sdk_mcp_server, tool


DEFAULT_START_DATE = "1990-12-19"
DEFAULT_FIELDS = (
    "date,code,open,high,low,close,preclose,volume,amount,turn,"
    "tradestatus,pctChg,peTTM,pbMRQ,psTTM,pcfNcfTTM,isST"
)
DEFAULT_VALUATION_FIELDS = "date,code,close,peTTM,pbMRQ,psTTM,pcfNcfTTM"

FINANCE_QUERY_MAP: Dict[str, Callable[..., Any]] = {
    "profit": bs.query_profit_data,
    "operation": bs.query_operation_data,
    "growth": bs.query_growth_data,
    "balance": bs.query_balance_data,
    "cash_flow": bs.query_cash_flow_data,
    "dupont": bs.query_dupont_data,
}


@contextmanager
def _baostock_session() -> Iterable[None]:
    """
    维护一次 baostock 会话，确保登录退出成对执行。
    """

    login_result = bs.login()
    if login_result.error_code != "0":
        raise RuntimeError(f"baostock 登录失败: {login_result.error_msg}")
    try:
        yield
    finally:
        bs.logout()


def _normalize_date(value: str | None, fallback: str | None = None) -> str | None:
    """
    转换日期字符串为YYYY-MM-DD格式，必要时使用默认值。
    """

    if not value and fallback:
        return fallback
    if not value:
        return None
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return fallback
    return parsed.strftime("%Y-%m-%d")  # type: ignore[arg-type]


def _coalesce_fields(raw_fields: Any, default: str = DEFAULT_FIELDS) -> str:
    """
    统一字段入参，可接受字符串或列表。
    """

    if raw_fields is None:
        return default
    if isinstance(raw_fields, str):
        return raw_fields
    if isinstance(raw_fields, (list, tuple, set)):
        return ",".join(str(field) for field in raw_fields)
    raise ValueError("fields 仅支持字符串或字符串列表")


def _baostock_dataframe(response: Any) -> pd.DataFrame:
    """
    将 baostock ResultSet 转换为 DataFrame。
    """

    if hasattr(response, "error_code") and response.error_code != "0":
        raise RuntimeError(f"baostock 查询失败: {response.error_msg}")
    if hasattr(response, "get_data"):
        df_data = response.get_data()
        if isinstance(df_data, pd.DataFrame):
            return df_data
    data_list: List[List[str]] = []
    while (getattr(response, "error_code", "1") == "0") and response.next():
        data_list.append(response.get_row_data())
    return pd.DataFrame(data_list, columns=getattr(response, "fields", []))


def _format_dataframe_response(df_data: pd.DataFrame) -> Dict[str, Any]:
    """
    将 DataFrame 序列化为 MCP 标准响应。
    """

    return {
        "content": [
            {
                "type": "text",
                "text": str(df_data.to_dict("records")),
            }
        ]
    }


def _format_error_response(message: str) -> Dict[str, Any]:
    """
    构建统一的错误响应。
    """

    return {
        "content": [
            {
                "type": "text",
                "text": message,
            }
        ]
    }


def _ensure_code(code: str | None) -> str:
    """
    校验股票或指数代码，确保存在市场前缀。
    """

    if not code:
        raise ValueError("必须提供代码，格式如 sh.600000 / sz.000001")
    trimmed = code.strip()
    if "." not in trimmed:
        raise ValueError("代码需携带交易所前缀，例如 sh.600000")
    return trimmed


def _format_saved_path_response(saved_path: str) -> Dict[str, Any]:
    """
    构建仅返回保存路径的响应。
    """

    return {
        "content": [
            {
                "type": "text",
                "text": f"数据已保存至：{saved_path}",
            }
        ]
    }


def _parse_bool(value: Any) -> bool:
    """
    将具有常见表示的布尔值规范化。
    """

    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "y"}:
            return True
        if lowered in {"0", "false", "no", "n"}:
            return False
    raise ValueError("save_to_file 仅支持布尔值或 true/false 形式字符串")


def _save_dataframe_if_needed(
    df_data: pd.DataFrame, args: Dict[str, Any]
) -> Optional[str]:
    """
    在需要时保存 DataFrame 为 parquet，并返回绝对路径。
    """

    if "save_to_file" not in args and "save_file_path" not in args:
        return None

    flag = args.get("save_to_file")
    if flag is None:
        raise ValueError("启用保存功能时必须提供 save_to_file 参数")
    try:
        should_save = _parse_bool(flag)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc

    if not should_save:
        return None

    file_path = args.get("save_file_path")
    if not file_path:
        raise ValueError("启用保存功能时必须提供 save_file_path")

    path = Path(file_path).expanduser()
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    suffix = path.suffix.lower()
    path.parent.mkdir(parents=True, exist_ok=True)
    if suffix == ".csv":
        df_data.to_csv(path, index=False)
    elif suffix in {".pqt", ".parquet"}:
        df_data.to_parquet(path, index=False)
    elif suffix == ".pkl":
        df_data.to_pickle(path)
    else:
        raise ValueError("save_file_path 仅支持 .csv/.pqt/.parquet/.pkl 扩展名")
    return str(path)


@tool(
    name="baostock_a_share_kline",
    description="查询A股K线数据，支持日/周/月及分钟级别，含可选复权与估值字段",
    input_schema={
        "code": {"type": "string", "description": "股票代码，形如 sh.600000"},
        "start_date": {
            "type": "string",
            "description": "起始日期YYYY-MM-DD，默认1990-12-19",
        },
        "end_date": {
            "type": "string",
            "description": "截止日期YYYY-MM-DD，默认当天",
        },
        "frequency": {
            "type": "string",
            "description": "频率 d/w/m/5/15/30/60，默认d",
        },
        "adjust_flag": {
            "type": "string",
            "description": "复权类型 1前复权/2后复权/3不复权，默认3",
        },
        "fields": {
            "type": ["string", "array"],
            "description": "需要的字段，默认含价量与估值字段",
        },
        "save_to_file": {
            "type": ["boolean", "string"],
            "description": "是否将结果保存为parquet，需配合save_file_path",
        },
        "save_file_path": {
            "type": "string",
            "description": "保存parquet文件的目标路径，可为相对路径",
        },
    },
)
async def baostock_a_share_kline_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    获取A股历史K线数据。

    :param args: MCP 传入的参数字典。
    :type args: dict
    :returns: K线记录序列。
    :rtype: dict
    :raises ValueError: 当代码或参数非法时。
    """

    try:
        code = _ensure_code(args.get("code"))
    except ValueError as exc:
        return _format_error_response(str(exc))
    start_date = _normalize_date(args.get("start_date"), DEFAULT_START_DATE)
    end_date = _normalize_date(
        args.get("end_date"), dt.date.today().strftime("%Y-%m-%d")
    )
    frequency = args.get("frequency", "d")
    adjust_flag = args.get("adjust_flag", "3")
    try:
        fields = _coalesce_fields(args.get("fields"))
    except ValueError as exc:
        return _format_error_response(str(exc))

    try:
        with _baostock_session():
            rs = bs.query_history_k_data_plus(
                code=code,
                fields=fields,
                start_date=start_date,
                end_date=end_date,
                frequency=frequency,
                adjustflag=adjust_flag,
            )
            df_data = _baostock_dataframe(rs)
        if df_data.empty:
            return _format_error_response("未查询到符合条件的K线数据")
        try:
            saved_path = _save_dataframe_if_needed(df_data, args)
        except ValueError as exc:
            return _format_error_response(str(exc))
        if saved_path:
            return _format_saved_path_response(saved_path)
        return _format_dataframe_response(df_data)
    except Exception as exc:  # pragma: no cover - 防御性返回
        return _format_error_response(f"获取A股K线失败：{exc}")


@tool(
    name="baostock_index_kline",
    description="查询指数K线数据，支持上证、深证及主要宽基指数",
    input_schema={
        "code": {"type": "string", "description": "指数代码，例：sh.000001、sz.399001"},
        "start_date": {
            "type": "string",
            "description": "起始日期YYYY-MM-DD，默认1990-12-19",
        },
        "end_date": {
            "type": "string",
            "description": "截止日期YYYY-MM-DD，默认当天",
        },
        "frequency": {
            "type": "string",
            "description": "频率 d/w/m/5/15/30/60，默认d",
        },
        "fields": {
            "type": ["string", "array"],
            "description": "返回字段，默认使用A股字段集合",
        },
        "save_to_file": {
            "type": ["boolean", "string"],
            "description": "是否将结果保存为parquet，需配合save_file_path",
        },
        "save_file_path": {
            "type": "string",
            "description": "保存parquet文件的目标路径，可为相对路径",
        },
    },
)
async def baostock_index_kline_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    获取指数历史K线数据。

    :param args: MCP 参数。
    :type args: dict
    :returns: 指数K线。
    :rtype: dict
    """

    try:
        code = _ensure_code(args.get("code"))
    except ValueError as exc:
        return _format_error_response(str(exc))
    start_date = _normalize_date(args.get("start_date"), DEFAULT_START_DATE)
    end_date = _normalize_date(
        args.get("end_date"), dt.date.today().strftime("%Y-%m-%d")
    )
    frequency = args.get("frequency", "d")
    try:
        fields = _coalesce_fields(args.get("fields"))
    except ValueError as exc:
        return _format_error_response(str(exc))

    try:
        with _baostock_session():
            rs = bs.query_history_k_data_plus(
                code=code,
                fields=fields,
                start_date=start_date,
                end_date=end_date,
                frequency=frequency,
                adjustflag="3",
            )
            df_data = _baostock_dataframe(rs)
        if df_data.empty:
            return _format_error_response("未查询到指数K线数据")
        try:
            saved_path = _save_dataframe_if_needed(df_data, args)
        except ValueError as exc:
            return _format_error_response(str(exc))
        if saved_path:
            return _format_saved_path_response(saved_path)
        return _format_dataframe_response(df_data)
    except Exception as exc:  # pragma: no cover
        return _format_error_response(f"获取指数K线失败：{exc}")


@tool(
    name="baostock_valuation_daily",
    description="获取估值指标(日频)，含市盈率、市净率、市销率等",
    input_schema={
        "code": {"type": "string", "description": "股票代码，形如 sh.600000"},
        "start_date": {
            "type": "string",
            "description": "起始日期YYYY-MM-DD，默认1990-12-19",
        },
        "end_date": {
            "type": "string",
            "description": "截止日期YYYY-MM-DD，默认当天",
        },
        "fields": {
            "type": ["string", "array"],
            "description": "估值指标字段，默认包含pe/pb/ps/pcf",
        },
        "save_to_file": {
            "type": ["boolean", "string"],
            "description": "是否将结果保存为parquet，需配合save_file_path",
        },
        "save_file_path": {
            "type": "string",
            "description": "保存parquet文件的目标路径，可为相对路径",
        },
    },
)
async def baostock_valuation_daily_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    查询日频估值指标。

    :param args: MCP 参数。
    :type args: dict
    :returns: 估值记录。
    :rtype: dict
    """

    try:
        code = _ensure_code(args.get("code"))
    except ValueError as exc:
        return _format_error_response(str(exc))
    start_date = _normalize_date(args.get("start_date"), DEFAULT_START_DATE)
    end_date = _normalize_date(
        args.get("end_date"), dt.date.today().strftime("%Y-%m-%d")
    )
    try:
        fields = _coalesce_fields(args.get("fields"), DEFAULT_VALUATION_FIELDS)
    except ValueError as exc:
        return _format_error_response(str(exc))

    try:
        with _baostock_session():
            rs = bs.query_history_k_data_plus(
                code=code,
                fields=fields,
                start_date=start_date,
                end_date=end_date,
                frequency="d",
                adjustflag="3",
            )
            df_data = _baostock_dataframe(rs)
        if df_data.empty:
            return _format_error_response("未查询到估值指标数据")
        try:
            saved_path = _save_dataframe_if_needed(df_data, args)
        except ValueError as exc:
            return _format_error_response(str(exc))
        if saved_path:
            return _format_saved_path_response(saved_path)
        return _format_dataframe_response(df_data)
    except Exception as exc:  # pragma: no cover
        return _format_error_response(f"获取估值指标失败：{exc}")


@tool(
    name="baostock_stock_basic",
    description="查询证券基本资料，支持按代码或模糊名称过滤",
    input_schema={
        "code": {"type": "string", "description": "证券代码，可为空获取全部"},
        "code_name": {
            "type": "string",
            "description": "证券名称（可模糊），与code二选一",
        },
        "save_to_file": {
            "type": ["boolean", "string"],
            "description": "是否将结果保存为parquet，需配合save_file_path",
        },
        "save_file_path": {
            "type": "string",
            "description": "保存parquet文件的目标路径，可为相对路径",
        },
    },
)
async def baostock_stock_basic_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    查询证券基本资料。

    :param args: MCP 参数。
    :type args: dict
    :returns: 基础资料表。
    :rtype: dict
    """

    code = args.get("code")
    code_name = args.get("code_name")
    try:
        with _baostock_session():
            rs = bs.query_stock_basic(code=code, code_name=code_name)
            df_data = _baostock_dataframe(rs)
        if df_data.empty:
            return _format_error_response("未查询到证券基本资料")
        try:
            saved_path = _save_dataframe_if_needed(df_data, args)
        except ValueError as exc:
            return _format_error_response(str(exc))
        if saved_path:
            return _format_saved_path_response(saved_path)
        return _format_dataframe_response(df_data)
    except Exception as exc:  # pragma: no cover
        return _format_error_response(f"获取证券基本资料失败：{exc}")


@tool(
    name="baostock_financial_quarterly",
    description="获取季频财务指标（盈利/营运/成长/偿债/现金流/杜邦）",
    input_schema={
        "code": {"type": "string", "description": "股票代码，形如 sh.600000"},
        "year": {"type": "integer", "description": "年份，例如 2023"},
        "quarter": {
            "type": "integer",
            "description": "季度，取值1/2/3/4",
        },
        "report_type": {
            "type": "string",
            "enum": list(FINANCE_QUERY_MAP.keys()),
            "description": "指标类型：profit/operation/growth/balance/cash_flow/dupont",
        },
        "save_to_file": {
            "type": ["boolean", "string"],
            "description": "是否将结果保存为parquet，需配合save_file_path",
        },
        "save_file_path": {
            "type": "string",
            "description": "保存parquet文件的目标路径，可为相对路径",
        },
    },
)
async def baostock_financial_quarterly_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    查询季频财务指标。

    :param args: MCP 参数。
    :type args: dict
    :returns: 季度财务指标表。
    :rtype: dict
    """

    try:
        code = _ensure_code(args.get("code"))
    except ValueError as exc:
        return _format_error_response(str(exc))
    year = args.get("year")
    quarter = args.get("quarter")
    report_type = args.get("report_type")
    if report_type not in FINANCE_QUERY_MAP:
        return _format_error_response("report_type 取值不合法")
    if year is None or quarter is None:
        return _format_error_response("year 与 quarter 均为必填参数")
    if int(quarter) not in {1, 2, 3, 4}:
        return _format_error_response("quarter 仅支持 1/2/3/4")

    query_func = FINANCE_QUERY_MAP[report_type]
    try:
        with _baostock_session():
            rs = query_func(code=code, year=int(year), quarter=int(quarter))
            df_data = _baostock_dataframe(rs)
        if df_data.empty:
            return _format_error_response("未查询到季频财务数据")
        try:
            saved_path = _save_dataframe_if_needed(df_data, args)
        except ValueError as exc:
            return _format_error_response(str(exc))
        if saved_path:
            return _format_saved_path_response(saved_path)
        return _format_dataframe_response(df_data)
    except Exception as exc:  # pragma: no cover
        return _format_error_response(f"获取季频财务数据失败：{exc}")


MCP_NAME = "tradex_baostock_tools"
MCP_TOOLS = [
    "baostock_a_share_kline",
    "baostock_index_kline",
    "baostock_valuation_daily",
    "baostock_stock_basic",
    "baostock_financial_quarterly",
]
__mcp__ = create_sdk_mcp_server(
    name=MCP_NAME,
    tools=[
        baostock_a_share_kline_tool,
        baostock_index_kline_tool,
        baostock_valuation_daily_tool,
        baostock_stock_basic_tool,
        baostock_financial_quarterly_tool,
    ],
)
__mcp_allowed_tools__ = [f"mcp__{MCP_NAME}__{tool}" for tool in MCP_TOOLS]
