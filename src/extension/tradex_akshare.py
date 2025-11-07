import akshare
import pandas as pd
import datetime as dt

from typing import Any, Dict

from claude_agent_sdk import tool, create_sdk_mcp_server


def _safe_get_date(date_str: str) -> str:
    pd_ts = pd.to_datetime(date_str, errors="coerce")
    if pd_ts is pd.NaT:
        return dt.date.today().strftime("%Y%m%d")
    else:
        return pd_ts.strftime("%Y%m%d") # type: ignore


def _format_dataframe_response(df_data: pd.DataFrame) -> Dict[str, Any]:
    return {
        "content": [
            {
                "type": "text",
                "text": str(df_data.to_dict("records")),
            }
        ]
    }


def _format_error_response(message: str) -> Dict[str, Any]:
    return {
        "content": [
            {
                "type": "text",
                "text": message,
            }
        ]
    }



@tool(
    name="stock_zt_pool",
    description="获取当日涨停股票池",
    input_schema={
        "date": {"type": "string", "description": "日期，格式YYYYMMDD，默认为当天日期，例：20230405"}
    },
)
async def stock_zt_pool_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    date = args.get("date", dt.date.today().strftime("%Y%m%d"))
    date = _safe_get_date(date)
    try:
        df_data = akshare.stock_zt_pool_em(date)
        return _format_dataframe_response(df_data)
    except Exception as e:
        return _format_error_response(f"获取涨停股票池失败，错误信息：{e}")


@tool(
    name="stock_zt_pool_previous",
    description="获取昨日涨停股票池",
    input_schema={
        "date": {"type": "string", "description": "日期，格式YYYYMMDD，默认为当天日期，例：20230405"}
    },
)
async def stock_zt_pool_previous_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    date = args.get("date", dt.date.today().strftime("%Y%m%d"))
    date = _safe_get_date(date)
    try:
        df_data = akshare.stock_zt_pool_previous_em(date)
        return _format_dataframe_response(df_data)
    except Exception as e:
        return _format_error_response(f"获取昨日涨停股票池失败，错误信息：{e}")


@tool(
    name="stock_zt_pool_strong",
    description="获取涨停强势股池",
    input_schema={
        "date": {"type": "string", "description": "日期，格式YYYYMMDD，默认为当天日期，例：20230405"}
    },
)
async def stock_zt_pool_strong_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    date = args.get("date", dt.date.today().strftime("%Y%m%d"))
    date = _safe_get_date(date)
    try:
        df_data = akshare.stock_zt_pool_strong_em(date)
        return _format_dataframe_response(df_data)
    except Exception as e:
        return _format_error_response(f"获取涨停强势股池失败，错误信息：{e}")


@tool(
    name="stock_zt_pool_sub_new",
    description="获取涨停次新股池",
    input_schema={
        "date": {"type": "string", "description": "日期，格式YYYYMMDD，默认为当天日期，例：20230405"}
    },
)
async def stock_zt_pool_sub_new_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    date = args.get("date", dt.date.today().strftime("%Y%m%d"))
    date = _safe_get_date(date)
    try:
        df_data = akshare.stock_zt_pool_sub_new_em(date)
        return _format_dataframe_response(df_data)
    except Exception as e:
        return _format_error_response(f"获取涨停次新股池失败，错误信息：{e}")


@tool(
    name="stock_zt_pool_zbgc",
    description="获取炸板股池",
    input_schema={
        "date": {"type": "string", "description": "日期，格式YYYYMMDD，默认为当天日期，例：20230405"}
    },
)
async def stock_zt_pool_zbgc_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    date = args.get("date", dt.date.today().strftime("%Y%m%d"))
    date = _safe_get_date(date)
    try:
        df_data = akshare.stock_zt_pool_zbgc_em(date)
        return _format_dataframe_response(df_data)
    except Exception as e:
        return _format_error_response(f"获取炸板股池失败，错误信息：{e}")


@tool(
    name="stock_zt_pool_dtgc",
    description="获取跌停股池",
    input_schema={
        "date": {"type": "string", "description": "日期，格式YYYYMMDD，默认为当天日期，例：20230405"}
    },
)
async def stock_zt_pool_dtgc_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    date = args.get("date", dt.date.today().strftime("%Y%m%d"))
    date = _safe_get_date(date)
    try:
        df_data = akshare.stock_zt_pool_dtgc_em(date)
        return _format_dataframe_response(df_data)
    except Exception as e:
        return _format_error_response(f"获取跌停股池失败，错误信息：{e}")

@tool(
    name="stock_info_global_em",
    description="获取全球财经快讯",
    input_schema={},
)
async def stock_info_global_em_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    try:
        df_data = akshare.stock_info_global_em()
        if "链接" in df_data.columns:
            df_data = df_data.drop(columns=["链接"])
        return _format_dataframe_response(df_data)
    except Exception as e:
        return _format_error_response(f"获取全球财经快讯失败，错误信息：{e}")


MCP_NAME = "tradex_akshare_tools"
MCP_TOOLS = [
    "stock_zt_pool",
    "stock_zt_pool_previous",
    "stock_zt_pool_strong",
    "stock_zt_pool_sub_new",
    "stock_zt_pool_zbgc",
    "stock_zt_pool_dtgc",
    "stock_info_global_em"
]
__mcp__ = create_sdk_mcp_server(
    name=MCP_NAME,
    tools=[
        stock_zt_pool_tool,
        stock_zt_pool_previous_tool,
        stock_zt_pool_strong_tool,
        stock_zt_pool_sub_new_tool,
        stock_zt_pool_zbgc_tool,
        stock_zt_pool_dtgc_tool,
        stock_info_global_em_tool
    ],
)
__mcp_allowed_tools__ = [F"mcp__{MCP_NAME}__{tool}" for tool in MCP_TOOLS]
