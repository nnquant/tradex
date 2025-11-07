import tomllib, asyncio, importlib

from typing import Any, Dict, List, Optional, Tuple, Union
from pathlib import Path
from loguru import logger
from textual.widgets import Input
from tradex_tui import AgentApp, AgentController

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient
from claude_agent_sdk import AssistantMessage, UserMessage, ResultMessage, SystemMessage
from claude_agent_sdk import TextBlock, ToolUseBlock, ToolResultBlock, ThinkingBlock
from claude_agent_sdk import PermissionResultAllow, PermissionResultDeny

from .utils.prompt import get_prompt
from .utils.log import setup_log

from src.extension import tradex_easytrader, tradex_akshare

_SRC_DIR = Path(__file__).parent

class TradexApp(AgentApp):
    
    def __init__(self, config: Dict[str, Any]) -> None:
        super().__init__()
        self.config = config
        self.claude_client: ClaudeSDKClient | None = None

        self.system_prompt = ""
    
    async def on_ready(self):
        # self.controller.notify("connected to agent backend", level="information")
        self.controller.add_log_message("tradex - 系统正在初始化", "info")
        await self.init()
        self.controller.clear()
        self.controller.add_welcome_screen(self.config)
        self.console.set_window_title("Tradex")

    async def on_exit(self):
        if self.claude_client:
            await self.claude_client.disconnect()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        # await super().on_input_submitted(event)
        text = event.value.strip()
        if text:
             self.run_worker(self.handle_user_input(text))

    async def init(self):
        environment_config = self.config.get("environment")
        if environment_config is None:
            raise ValueError("Missing 'environment' configuration")
        
        cwd = environment_config.get("cwd")
        project = environment_config.get("project")
        if not cwd:
            cwd = Path.home()
            cwd = Path.cwd()
        else:
            cwd = Path(cwd)
        cwd = cwd
        if project:
            cwd = cwd / project
        cwd.mkdir(parents=True, exist_ok=True)

        setup_log(str(cwd / ".tradex" / "tradex.log"))

        envs = {}
        model_config = self.config.get("model", {})
        if model_config is None:
            raise ValueError("Missing 'model' configuration")
        if model_config.get("base_url"):
            envs["ANTHROPIC_BASE_URL"] = model_config.get("base_url")
        if model_config.get("api_key"):
            envs["ANTHROPIC_AUTH_TOKEN"] = model_config.get("api_key")
        if model_config.get("model_name"):
            envs["ANTHROPIC_MODEL"] = model_config.get("model_name")
        if model_config.get("fast_model_name"):
            envs["ANTHROPIC_SMALL_FAST_MODEL"] = model_config.get("fast_model_name")
        
        agent_config = self.config.get("agent", {})
        if agent_config is None:
            raise ValueError("Missing 'agent' configuration")

        extension_enabled = agent_config.get("extension_enabled", [])
        extension_config = self.config.get("extensions", {})
        extension_options = self.config.get("extension", {})
        mcp_servers, allowed_tools = self.init_extensions_from_config(extension_config, extension_options, extension_enabled)

        self.system_prompt = get_prompt(_SRC_DIR / "prompts" / "system.md")
        options = ClaudeAgentOptions(
            system_prompt="你是tradex，一个专注于投资与交易的AI助手，运行在支持代码生成与MCP工具调用的环境中。核心目标：通过写代码和调用工具完成数据获取、分析与下单协助。",
            # system_prompt={
            #     "type": "preset",
            #     "preset": "claude_code",
            #     "append": "你是tradex，一个专注于投资与交易的AI助手，运行在支持代码生成与MCP工具调用的环境中。核心目标：通过写代码和调用工具完成数据获取、分析与下单协助。"
            # },
            permission_mode=agent_config.get("permission_mode"),
            cwd=str(cwd),
            env=envs,
            can_use_tool=self.prompt_for_tool_approval, # type: ignore
            mcp_servers=mcp_servers, # type: ignore
            allowed_tools=allowed_tools,
        )

        self.claude_client = ClaudeSDKClient(options)
        await self.claude_client.connect()

    def init_extensions_from_config(self, extension_config: Dict[str, Any], extension_options: Dict[str, Any], extension_enabled: List[str] = []):
        mcp_servers = {}
        allowed_tools = []
        self.controller.add_log_message(f"tradex - 已启用的扩展: {', '.join(extension_enabled)}", "info")
        for k, v in extension_config.items():
            if extension_enabled and k not in extension_enabled:
                continue
            self.controller.add_log_message(f"tradex - 加载扩展 {k}", "info")
            module_path = v["path"]
            ext_moudle = importlib.import_module(module_path)
            mcp_name = getattr(ext_moudle, "MCP_NAME", None)
            ext_mcp = getattr(ext_moudle, "__mcp__", None)
            ext_allowed_tools = getattr(ext_moudle, "__mcp_allowed_tools__", [])
            init_func = getattr(ext_moudle, "init_extension", None)
            try:
                mcp_servers[mcp_name] = ext_mcp
                allowed_tools.extend(ext_allowed_tools)
                if init_func:
                    init_func(extension_options.get(k, {}), self.controller)
            except Exception as e:
                continue
        return mcp_servers, allowed_tools

    async def handle_user_input(self, user_input: str):
        if not self.claude_client:
            return

        await self.claude_client.query(f"{self.system_prompt}\n\n{user_input}")

        async for message in self.claude_client.receive_messages():
            self.handle_message(message)

    def handle_message(self, msg):
        def _handle_mcp_tool_use(tool_name: str):
            if tool_name.startswith("mcp"):
                tool_name = tool_name.split("__")[-1]
                return tool_name
            return tool_name

        logger.info(msg)
        if isinstance(msg, AssistantMessage):
            for content in msg.content:
                if isinstance(content, TextBlock):
                    self.controller.add_message(text=content.text)
                elif isinstance(content, ToolUseBlock):
                    if content.name == "TodoWrite":
                        todos = content.input.get("todos", [])
                        self.controller.add_todo_list(todos)
                        return
                    tool_name = _handle_mcp_tool_use(content.name)
                    self.controller.add_tool_use(name=tool_name, input=content.input)
        elif isinstance(msg, UserMessage):
            for content in msg.content:
                if isinstance(content, ToolResultBlock):
                    if isinstance(content.content, str):
                        if content.content.find("Todos") != -1:
                            return
                    self.controller.add_tool_use_result(content.is_error, content.content) # type: ignore

    async def prompt_for_tool_approval(self, tool_name, input_params, *args, **kwargs):
        future = asyncio.Future()
        self.controller.add_tool_use_approval(future, tool_name, input_params)
        result = await future
        if result:
            return PermissionResultAllow()
        else:
            return PermissionResultDeny()
