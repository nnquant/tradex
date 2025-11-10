import asyncio, importlib
import inspect
import json
import platform
import uuid
from datetime import datetime, timezone

from typing import Any, Dict, List, Optional, Tuple, Union
from pathlib import Path
from loguru import logger
from textual.widgets import Input
from tradex_tui import AgentApp, AgentController

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient
from claude_agent_sdk import AssistantMessage, UserMessage, ResultMessage, SystemMessage
from claude_agent_sdk import TextBlock, ToolUseBlock, ToolResultBlock, ThinkingBlock
from claude_agent_sdk import PermissionResultAllow, PermissionResultDeny

from .utils.prompt import render_prompt
from .utils.log import setup_log
from .utils.config import load_config


_SRC_DIR = Path(__file__).parent

class TradexApp(AgentApp):
    
    def __init__(self, config_path: str | Path) -> None:
        super().__init__()
        self.config_path = Path(config_path).resolve()
        if not self.config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {self.config_path}")
        self.config = load_config(str(self.config_path))
        self.claude_client: ClaudeSDKClient | None = None
        self.system_prompt = ""
        self.cwd: Path | None = None
        self.base_cwd: Path | None = None
        self.storage_root: Path | None = None
        self.session_id: str | None = None
        self.session_history: list[Dict[str, Any]] = []
        self.session_started_at: str | None = None
    
    async def on_ready(self):
        self.controller.add_log_message("Tradex - 系统正在初始化", "info")
        await self.init()
        self.controller.clear()
        self.controller.add_welcome_screen(self.config)
        self.console.set_window_title("Tradex")

    async def on_exit(self):
        self._save_session_history()
        if self.claude_client:
            await self.claude_client.disconnect()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            return
        if self._handle_command(text):
            event.input.value = ""
            return
        self._append_session_event("user_input", {"text": text})
        self.run_worker(self.handle_user_input(text))

    async def init(self):
        environment_config = self.config.get("environment")
        if environment_config is None:
            raise ValueError("Missing 'environment' configuration")
        
        cwd_config = environment_config.get("cwd")
        project = environment_config.get("project")
        base_cwd = Path(cwd_config).expanduser() if cwd_config else Path.cwd()
        if project:
            base_cwd = base_cwd / project
        self.base_cwd = base_cwd

        workspace_dir = base_cwd / "workspace"
        timestamp = datetime.now().astimezone()
        run_cwd = workspace_dir / timestamp.strftime("%Y%m%d%H%M%S")
        run_cwd.mkdir(parents=True, exist_ok=True)
        cwd = run_cwd
        self.cwd = cwd

        storage_root = base_cwd / ".tradex"
        storage_root.mkdir(parents=True, exist_ok=True)
        self.storage_root = storage_root
        log_path = (storage_root / "tradex.log").resolve()
        setup_log(str(log_path))

        self.session_id = str(uuid.uuid4())
        self.session_started_at = datetime.now().astimezone().isoformat()
        self.session_history = []

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
        ctx = {"workspace": str(cwd)}
        mcp_servers, allowed_tools = self.init_extensions_from_config(
            extension_config,
            extension_options,
            extension_enabled,
            ctx=ctx,
        )

        prompt_context = {
            "ENV_CWD": str(cwd),
            "ENV_PLATFORM": platform.platform(),
            "ENV_DATETIME": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S %Z"),
        }
        self.system_prompt = render_prompt(_SRC_DIR / "prompts" / "system.md", prompt_context)
        options = ClaudeAgentOptions(
            system_prompt="你是tradex，一个专注于投资与交易的AI助手。核心目标：通过写代码和调用工具完成数据获取、分析与下单协助。",
            permission_mode=agent_config.get("permission_mode"),
            cwd=str(cwd),
            env=envs,
            can_use_tool=self.prompt_for_tool_approval, # type: ignore
            mcp_servers=mcp_servers, # type: ignore
            allowed_tools=allowed_tools,
            setting_sources=[]
        )

        self.claude_client = ClaudeSDKClient(options)
        await self.claude_client.connect()

    def init_extensions_from_config(
        self,
        extension_config: Dict[str, Any],
        extension_options: Dict[str, Any],
        extension_enabled: List[str] = [],
        ctx: Dict[str, Any] | None = None,
    ):
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
                    config = extension_options.get(k, {})
                    if ctx is None:
                        init_func(config, self.controller)
                    else:
                        sig = inspect.signature(init_func)
                        params = sig.parameters.values()
                        supports_ctx = any(
                            param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
                            for param in params
                        ) or len(params) >= 3
                        if supports_ctx:
                            init_func(config, self.controller, ctx)
                        else:
                            init_func(config, self.controller)
            except Exception as e:
                continue
        return mcp_servers, allowed_tools

    async def handle_user_input(self, user_input: str):
        if not self.claude_client:
            return

        self.controller.set_work_indicator(True, "Tradex is working in progress ...")
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
            assistant_record = {"text_blocks": [], "tool_calls": [], "thinking": []}
            for content in msg.content:
                if isinstance(content, TextBlock):
                    self.controller.add_message(text=content.text)
                    assistant_record["text_blocks"].append(content.text)
                elif isinstance(content, ThinkingBlock):
                    assistant_record["thinking"].append(getattr(content, "text", ""))
                elif isinstance(content, ToolUseBlock):
                    if content.name == "TodoWrite":
                        todos = content.input.get("todos", [])
                        in_progress = next(
                            (
                                item.get("content")
                                for item in todos
                                if isinstance(item, dict) and item.get("status") == "in_progress"
                            ),
                            None,
                        )
                        indicator_message = '正在' + str(in_progress) if in_progress else "Tradex is working in progress ..."
                        self.controller.set_work_indicator(True, indicator_message)
                        self.controller.add_todo_list(todos)
                        if assistant_record["text_blocks"] or assistant_record["tool_calls"] or assistant_record["thinking"]:
                            self._append_session_event("assistant_message", assistant_record)
                        self._append_session_event(
                            "assistant_todo",
                            {"todos": self._json_safe(todos), "indicator": indicator_message},
                        )
                        return
                    tool_name = _handle_mcp_tool_use(content.name)
                    self.controller.add_tool_use(name=tool_name, input=content.input)
                    assistant_record["tool_calls"].append(
                        {
                            "tool_name": tool_name,
                            "input": self._json_safe(content.input),
                            "tool_use_id": getattr(content, "id", None),
                        }
                    )
            if assistant_record["text_blocks"] or assistant_record["tool_calls"] or assistant_record["thinking"]:
                self._append_session_event("assistant_message", assistant_record)
        elif isinstance(msg, UserMessage):
            for content in msg.content:
                if isinstance(content, ToolResultBlock):
                    if isinstance(content.content, str):
                        if content.content.find("Todos") != -1:
                            return
                    payload = {
                        "is_error": content.is_error,
                        "content": self._json_safe(content.content),
                        "tool_use_id": getattr(content, "tool_use_id", None),
                    }
                    self.controller.add_tool_use_result(content.is_error, content.content) # type: ignore
                    self._append_session_event("tool_result", payload)
        elif isinstance(msg, SystemMessage):
            if getattr(msg, "subtype", "") == "init":
                self.controller.set_work_indicator(True, "Tradex is working in progress ...")
            self._append_session_event(
                "system_message",
                {"subtype": getattr(msg, "subtype", None), "content": getattr(msg, "content", None)},
            )
        elif isinstance(msg, ResultMessage):
            self.controller.set_work_indicator(False)
            duration_ms = getattr(msg, "duration_ms", None)
            duration_text = self._format_duration(duration_ms)
            self.controller.add_system_message(f"任务已完成，耗时{duration_text}")
            self._append_session_event(
                "result_message",
                {
                    "duration_ms": duration_ms,
                    "usage": self._json_safe(getattr(msg, "usage", None)),
                    "metadata": self._json_safe(getattr(msg, "metadata", None)),
                },
            )

    async def prompt_for_tool_approval(self, tool_name, input_params, *args, **kwargs):
        future = asyncio.Future()
        self.controller.add_tool_use_approval(future, tool_name, input_params)
        result = await future
        if result:
            return PermissionResultAllow()
        else:
            return PermissionResultDeny()

    def _append_session_event(self, event: str, payload: Dict[str, Any]) -> None:
        if not self.session_id:
            return
        record = {
            "event": event,
            "timestamp": datetime.now().astimezone().isoformat(),
            "payload": self._json_safe(payload),
        }
        self.session_history.append(record)

    def _json_safe(self, data: Any) -> Any:
        if isinstance(data, dict):
            return {k: self._json_safe(v) for k, v in data.items()}
        if isinstance(data, list):
            return [self._json_safe(item) for item in data]
        if isinstance(data, (str, int, float, bool)) or data is None:
            return data
        if isinstance(data, Path):
            return str(data)
        return str(data)

    def _save_session_history(self) -> None:
        if not self.session_id:
            return
        root = self.storage_root
        if not root and self.base_cwd:
            root = self.base_cwd / ".tradex"
        if not root:
            root = (self.cwd or Path.cwd()) / ".tradex"
        session_dir = root / "sessions" / self.session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        history_path = session_dir / "history.json"
        session_data = {
            "session_id": self.session_id,
            "started_at": self.session_started_at,
            "ended_at": datetime.now().astimezone().isoformat(),
            "cwd": str(self.cwd) if self.cwd else None,
            "history": self.session_history,
        }
        with history_path.open("w", encoding="utf-8") as fp:
            json.dump(session_data, fp, ensure_ascii=False, indent=2)

    def _handle_command(self, command: str) -> bool:
        """
        处理以斜杠开头的命令，返回 True 表示命令已消耗。
        """
        if command == "/model":
            self.msg_log.add_setting_dialog(self.config, self.config_path)
            return True
        return False

    @staticmethod
    def _format_duration(duration_ms: int | None) -> str:
        """
        将毫秒级耗时格式化为 ``xxh xxm xxs`` 形式，并自动省略为 ``00`` 的小时或分钟。

        :param duration_ms: 后端返回的耗时，单位为毫秒。
        :type duration_ms: int | None
        :returns: 去除冗余小时/分钟后的耗时字符串。
        :rtype: str
        """

        if duration_ms is None:
            return "0s"
        total_seconds = max(0, int(duration_ms) // 1000)
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60

        parts: list[str] = []
        if hours:
            parts.append(f"{hours:02d}h")
        if minutes:
            parts.append(f"{minutes:02d}m")
        parts.append(f"{seconds:02d}s")
        return " ".join(parts)
