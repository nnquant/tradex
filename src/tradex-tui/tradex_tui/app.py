from __future__ import annotations

import threading

from typing import Literal

from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.widgets import Input
from textual.binding import Binding

from .widgets.message_log import MessageLog
from .widgets.status_bar import StatusBar
from .widgets.approval import ApprovalModal, ApprovalResult
from .models import Message, ToolUse

class AgentController:
    """Public API to inject messages & drive the UI from your agent code. Use from threads/tasks."""
    def __init__(self, app: "AgentApp") -> None:
        self.app = app

    def _safe_call(self, fn, *args, **kwargs):
        if not getattr(self.app, "is_running", False):
            fn(*args, **kwargs)
            return

        app_thread_id = getattr(self.app, "_thread_id", None)
        if app_thread_id is None:
            driver = getattr(self.app, "_driver", None)
            driver_thread = getattr(driver, "_thread_id", None) or getattr(driver, "thread_id", None)
            app_thread_id = driver_thread

        current_thread_id = threading.get_ident()

        if app_thread_id is not None and app_thread_id == current_thread_id:
            fn(*args, **kwargs)
            return

        try:
            self.app.call_from_thread(fn, *args, **kwargs)
        except RuntimeError as error:
            if "call_from_thread" in str(error):
                # 同线程触发时直接执行，避免 Textual 的线程检查异常
                fn(*args, **kwargs)
            else:
                raise
    
    def clear(self) -> None:
        self._safe_call(self.app._clear)

    def notify(self, message: str, level: str = "information") -> None:
        self._safe_call(self.app._notify, message, level)

    def add_log_message(self, message: str, level: Literal["info", "warning", "error"]) -> None:
        self._safe_call(self.app._add_log_message, message, level)

    def add_user_message(self, text: str) -> None:
        self._safe_call(self.app._add_user_message, text)

    def add_system_message(self, text: str) -> None:
        self._safe_call(self.app._add_system_message, text)

    def add_message(self, text: str, role: str = "assistant", **meta) -> None:
        self._safe_call(self.app._add_message, Message(role=role, content=text, meta=meta)) # type: ignore

    def add_tool_use(self, name: str, input) -> None:
        tu = ToolUse(name=name, input=input)
        self._safe_call(self.app._add_tool_use, tu)
    
    def add_tool_use_result(self, is_error: bool, content: str):
        self._safe_call(self.app._add_tool_use_result, is_error, content)
    
    def add_tool_use_approval(self, approval_result, tool_name, input_params):
        self._safe_call(self.app._add_tool_use_approval, approval_result, tool_name, input_params)
    
    def add_todo_list(self, todo_list):
        self._safe_call(self.app._add_todo_list, todo_list)
    
    def add_welcome_screen(self, config):
        self._safe_call(self.app._add_welcome_screen, config)

    def set_status(self, **kwargs) -> None:
        self._safe_call(self.app._update_status, **kwargs)

class AgentApp(App):
    CSS = '''
    #message-log { height: 1fr; overflow-y: auto; }
    #status-bar { dock: bottom; height: 1; content-align: right middle; }
    #input { dock: bottom; }

    ToastRack {
        align: right top;
    }
    '''
    BINDINGS = [
        Binding("ctrl+c", "app.quit", "Quit"),
        Binding("ctrl+k", "clear_log", "Clear Log"),
        Binding("ctrl+l", "toggle_autoscroll", "AutoScroll"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.controller = AgentController(self)

    def compose(self) -> ComposeResult:
        self.msg_log = MessageLog()
        self.status = StatusBar()
        self.user_input = Input(placeholder="在这里输入消息", id="input")
        yield Vertical(self.msg_log, self.status, self.user_input)

    def _clear(self) -> None:
        self.msg_log.clear()

    def _notify(self, message: str, level: str = "information") -> None:
        self.app.notify(message, severity=level) # type: ignore

    def _add_log_message(self, message: str, level: Literal["info", "warning", "error"]) -> None:
        self.msg_log.add_log_message(message, level)

    def _add_message(self, m: Message) -> None:
        self.msg_log.add_markdown(m.content)

    def _add_user_message(self, text: str) -> None:
        self.msg_log.add_user_message(text)

    def _add_system_message(self, text: str) -> None:
        self.msg_log.add_system_message(text)

    def _add_tool_use(self, t: ToolUse) -> None:
        self.msg_log.add_tool_block(t.name, t.input)
    
    def _add_tool_use_result(self, is_error: bool, content: str):
        self.msg_log.add_tool_result_block(is_error, content)
    
    def _add_tool_use_approval(self, approval_result, tool_name, input_params):
        self.msg_log.add_tool_use_approval(approval_result, tool_name, input_params)
    
    def _add_todo_list(self, todo_list):
        self.msg_log.add_todo_list(todo_list)
    
    def _add_welcome_screen(self, config):
        self.msg_log.add_welcome_screen(config)

    def _update_status(self, **kwargs) -> None:
        for k, v in kwargs.items():
            if hasattr(self.status, k):
                setattr(self.status, k, v)

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if text:
            self._add_user_message(text)
            event.input.value = ""

    async def action_clear_log(self) -> None:
        for child in list(self.msg_log.children):
            await child.remove()

    async def action_toggle_autoscroll(self) -> None:
        self.msg_log.auto_scroll = not self.msg_log.auto_scroll
