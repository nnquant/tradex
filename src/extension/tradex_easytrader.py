import easytrader
import pandas as pd
import datetime as dt

from typing import Any, Dict
from pathlib import Path

from claude_agent_sdk import tool, create_sdk_mcp_server
from easytrader import grid_strategies


_easy_trader_client = None


def init_extension(config, ctl):
    global _easy_trader_client

    _easy_trader_client = easytrader.use(config.get("client_name", "ths"))
    xiadan_path = config.get("xiadan_path")
    if not xiadan_path:
        return
    
    ctl.add_log_message(f"tradex_easytrader - 正在连接到同花顺客户端: xiadan_path=[{xiadan_path}]", "info")
    try:
        _easy_trader_client.connect(config.get("xiadan_path")) # type: ignore
        _easy_trader_client.enable_type_keys_for_editor() # type: ignore
    except Exception as e:
        ctl.add_log_message(f"tradex_easytrader - 连接同花顺客户端失败: {e}", "error")


@tool(
    name="ths_query_balance",
    description="查询同花顺客户端账户资金",
    input_schema={
    }
)
async def ths_query_balance_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    if not _easy_trader_client:
        return {
            "content": [{
                "type": "text",
                "text": "未初始化 easytrader 客户端，请检查扩展配置。",
            }]
        }
    try:
        balance = _easy_trader_client.balance
        return {
            "content": [{
                "type": "text",
                "text": str(balance),
            }]
        }
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"查询账户资金失败，错误信息：{e}",
            }]
        }


@tool(
    name="ths_query_position",
    description="查询同花顺客户端持仓",
    input_schema={
    }
)
async def ths_query_position_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    if not _easy_trader_client:
        return {
            "content": [{
                "type": "text",
                "text": "未初始化 easytrader 客户端，请检查扩展配置。",
            }]
        }
    try:
        position = _easy_trader_client.position
        return {
            "content": [{
                "type": "text",
                "text": str(position),
            }]
        }
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"查询持仓失败，错误信息：{e}",
            }]
        }


@tool(
    name="ths_buy_stock",
    description="同花顺客户端买入股票",
    input_schema={
        "code": {"type": "string", "description": "6位股票代码，例：000001/600000/300750"},
        "price": {"type": "float", "description": "买入价格，例：10.5"},
        "amount": {"type": "integer", "description": "买入数量，例：100"}
    }
)
async def ths_buy_stock_tool(args: Dict[str, Any]) -> Dict[str, Any]:

    def _safe_code(code: str) -> str:
        """确保股票代码为6位，不足前面补0"""
        if '.' in code:
            code = code.split('.')[0]
        return code

    def _safe_price(price) -> float:
        if isinstance(price, str):
            return float(price)
        return price
    
    def _safe_amount(amount) -> int:
        if isinstance(amount, str):
            return int(amount)
        return amount

    if not _easy_trader_client:
        return {
            "content": [{
                "type": "text",
                "text": "未初始化 easytrader 客户端，请检查扩展配置。",
            }]
        }
    code = args.get("code")
    code = _safe_code(code) # type: ignore
    price = args.get("price")
    price = _safe_price(price)
    amount = args.get("amount")
    amount = _safe_amount(amount)

    try:
        result = _easy_trader_client.buy(code, price, amount) # type: ignore
        return {
            "content": [{
                "type": "text",
                "text": str(result),
            }]
        }
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"买入股票失败，错误信息：{e}",
            }]
        }


@tool(
    name="ths_sell_stock",
    description="同花顺客户端卖出股票",
    input_schema={
        "code": {"type": "string", "description": "6位股票代码，例：000001/600000/300750"},
        "price": {"type": "float", "description": "卖出价格，例：10.5"},
        "amount": {"type": "integer", "description": "卖出数量，例：100"}
    }
)
async def ths_sell_stock_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    if not _easy_trader_client:
        return {
            "content": [{
                "type": "text",
                "text": "未初始化 easytrader 客户端，请检查扩展配置。",
            }]
        }
    code = args.get("code")
    price = args.get("price")
    amount = args.get("amount")

    try:
        result = _easy_trader_client.sell(code, price, amount) # type: ignore
        return {
            "content": [{
                "type": "text",
                "text": str(result),
            }]
        }
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"卖出股票失败，错误信息：{e}",
            }]
        }


MCP_NAME = "tradex_easytrader"
MCP_TOOLS = [
    "ths_buy_stock",
    "ths_sell_stock"
]
MCP_DESCRIBE = "获得使用同花顺下单客户端买卖股票的能力"
__mcp__ = create_sdk_mcp_server(
    name=MCP_NAME,
    tools=[
        # ths_query_balance_tool,
        # ths_query_position_tool,
        ths_buy_stock_tool,
        ths_sell_stock_tool
    ],
)
__mcp_allowed_tools__ = [F"mcp__{MCP_NAME}__{tool}" for tool in MCP_TOOLS]
