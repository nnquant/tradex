# Tradex 扩展程序开发指南

本文档结合 `src/extension` 目录下现有实现（例如 `tradex_akshare.py`、`tradex_easytrader.py`）整理出一套可复用的扩展开发流程。目标是帮助你快速理解 Tradex 如何加载 MCP 扩展、如何定义工具，以及如何通过配置启用扩展。

## 1. 扩展运行时概览

1. Tradex 在 `src/tradex/app.py` 内通过 `init_extensions_from_config` 动态导入扩展模块，读取模块内的 `MCP_NAME`、`__mcp__`、`__mcp_allowed_tools__` 并注入到 Claude SDK 客户端。
2. 可选的 `init_extension(config, ctl)` 钩子在扩展加载时执行，用于初始化 SDK 客户端或做一次性的连接准备，例如 `tradex_easytrader.py` 在此阶段连接同花顺下单程序。
3. 工具必须使用 `claude_agent_sdk.tool` 装饰器声明，函数为 `async`，输入输出均为 JSON 结构，返回值包含 `content` 列表，示例可参考 `tradex_akshare.stock_zt_pool_tool`。

理解这三个阶段后，开发者即可根据业务需要添加数据源、交易接口或内部服务扩展。

## 2. 目录与命名约定

```
src/
└── extension/
    ├── tradex_akshare.py
    ├── tradex_easytrader.py
    └── your_extension.py   # 新增扩展模块
```

- 模块文件名使用 `snake_case`，并以 `tradex_` 前缀表明归属。
- 每个模块内建议至少包含：
  - `MCP_NAME`: MCP 服务名，需与工具列表保持一致。
  - `__mcp__`: 由 `create_sdk_mcp_server` 返回的服务器实例。
  - `__mcp_allowed_tools__`: 形如 `mcp__{MCP_NAME}__{tool}` 的字符串数组，供主程序做工具白名单校验。

## 3. 工具定义模板（基于 `tradex_akshare.py`）

```python
from claude_agent_sdk import tool, create_sdk_mcp_server

@tool(
    name="stock_zt_pool",
    description="获取当日涨停股票池",
    input_schema={
        "date": {"type": "string", "description": "日期，格式YYYYMMDD"}
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
```

开发要点：

1. **输入校验**：示例中的 `_safe_get_date` 将字符串转换为合法日期，这是保证 determinism 的关键步骤。
2. **统一返回结构**：`_format_dataframe_response` 将 `pandas.DataFrame` 转为 `List[Dict]` 后写入 `content`，方便前端直接渲染。
3. **错误可观测**：`_format_error_response` 明确返回错误文本，上层 UI 会在工具结果面板中展示。

照此模式即可定义更多 `@tool` 函数，再通过 `create_sdk_mcp_server` 注册：

```python
MCP_NAME = "tradex_akshare_tools"
__mcp__ = create_sdk_mcp_server(
    name=MCP_NAME,
    tools=[stock_zt_pool_tool, ...],
)
__mcp_allowed_tools__ = [f"mcp__{MCP_NAME}__{tool}" for tool in MCP_TOOLS]
```

## 4. 可选初始化钩子（参考 `tradex_easytrader.py`）

当扩展需要持久连接或依赖外部客户端时，可以实现 `init_extension(config, ctl)`：

```python
def init_extension(config, ctl):
    client_name = config.get("client_name", "ths")
    _easy_trader_client = easytrader.use(client_name)
    ctl.add_log_message(
        f"tradex_easytrader - 正在连接到同花顺客户端: xiadan_path=[{xiadan_path}]",
        "info",
    )
    _easy_trader_client.connect(config.get("xiadan_path"))
```

- `config` 来自 `tradex.config.toml` 中 `[extension.<name>]` 节点，可传入路径、凭证等私有参数。
- `ctl` 为 `AgentController`，可通过 `add_log_message` 向 TUI 输出初始化信息，方便排查连接问题。

若扩展不需要额外初始化，可省略该函数。

## 5. 配置与启用步骤

1. 在 `tradex.config.toml` 的 `[extensions]` 中登记模块路径（如 `src.extension.tradex_akshare`）。  
2. 在 `[agent]` 内的 `extension_enabled` 列表中写入需要启用的扩展名称。  
3. 如果扩展需要运行参数，在 `[extension.<name>]` 节点下填写，例如：

```toml
[extensions]
tradex_akshare = { path = "src.extension.tradex_akshare" }

[extension.tradex_akshare]
token = "your-token"
base_url = "https://api.example.com"
```

修改配置后重新启动 Tradex，日志面板中会看到“tradex - 加载扩展 xxx”以及扩展自定义的日志。

## 6. 质量与最佳实践

1. **显式依赖**：在模块顶部明确导入所有依赖包，保持“标准库 → 三方库 → 内部模块”顺序。
2. **异常处理**：任何调用外部 API/交易接口的地方都要捕获异常并返回可诊断的消息，必要时在日志中记录输入参数（敏感信息需脱敏）。
3. **同步限制**：所有工具函数必须是 `async def` 并避免阻塞调用；对非异步库可使用线程池或保证耗时短。
4. **文档化与示例**：为关键函数编写 reST 风格 docstring，必要时在本指南的基础上为新扩展补充 `README` 或内联示例。
5. **测试策略**：数据扩展可通过模拟输入参数与离线数据进行单元测试；交易扩展至少需要 dry-run 或沙箱验证，避免真实账户风险。

## 7. 常见问题排查

| 现象 | 排查思路 |
| --- | --- |
| 扩展未被加载 | 确认 `[agent].extension_enabled` 包含该扩展名，并检查 `[extensions]` 中 `path` 是否正确。 |
| 工具调用被拒绝 | `__mcp_allowed_tools__` 内容需与 `MCP_TOOLS` 一致，否则主程序不会放行。 |
| 工具执行报错 | 打开 `.tradex/tradex.log` 查看 `logger` 输出，或在工具内部增加 `ctl.add_log_message`。 |
| easytrader 无法交易 | 确认 `init_extension` 中的路径、客户端名称与实际安装一致，并确保运行环境有图形界面支持。 |

遵循以上流程即可快速为 Tradex 扩展新的数据工具或执行器，同时保证代码可维护、可审计。欢迎在新增扩展时将通用经验补充回本指南，形成迭代式的知识积累。
