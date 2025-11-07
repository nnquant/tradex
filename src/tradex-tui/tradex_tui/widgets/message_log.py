from __future__ import annotations
import re
import asyncio

from textual import messages, on
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static, Collapsible, Markdown, Label, ListView, ListItem, RadioButton, RadioSet, RichLog

from rich.panel import Panel
from rich.table import Table
from rich.console import RenderableType, Group
from rich.style import Style
from rich.text import Text

from typing import Any, List, Dict, Literal
from loguru import logger


def _patch_markdown_h1_render() -> None:
    from textual.widgets._markdown import MarkdownH1, MarkdownParagraph

    MarkdownH1.DEFAULT_CSS = """
    MarkdownH1 {
        content-align: left middle;
        background: $markdown-h1-background;
        text-style: $markdown-h1-text-style;
    }
    """
    Markdown.BLOCKS["h1"] = MarkdownH1

    MarkdownParagraph.DEFAULT_CSS = """
    Markdown > MarkdownParagraph {
         margin: 1 0 1 0;
    }
    """
    Markdown.BLOCKS["paragraph_open"] = MarkdownParagraph

_patch_markdown_h1_render()


class MsgBlock(Static):
    def __init__(self, body: RenderableType, **panel_kwargs) -> None:
        super().__init__("", classes="msg-block")
        self.body = body
        self.panel_kwargs = panel_kwargs

    def render(self) -> RenderableType:
        return Panel(self.body, **self.panel_kwargs)


class TodoBlock(Collapsible):

    def __init__(self, todo_content: List[Dict[str, str]]):
        self.todo_content = todo_content
        super().__init__(title=f"[b]Todo[/]", collapsed=True)

    def compose(self):
        radio_set = RadioSet(disabled=True)
        with radio_set:
            for i, todo_item in enumerate(self.todo_content):
                content = todo_item["content"]
                status = todo_item["status"]
                value = status == "completed"
                # active_form = todo_item["activeForm"]
                # is_active = active_form == content
                if status == "completed":
                    content_label = Text(content, style=Style(color="gray50", strike=True))
                elif status == "in_progress":
                    content_label = Text(content, style=Style(bold=True))
                elif status == "pending":
                    content_label = Text(content, style=Style(color="gray50"))
                else:
                    continue
                button = RadioButton(content_label, value=value)
                if status in ["in_progress", "completed"]:
                    button.action_toggle_button()
                yield button
            

class ToolBlock(Collapsible):
    # DEFAULT_CSS = 'ToolBlock { border: tall gray; }'

    def __init__(self, name: str, input_obj: Any) -> None:
        super().__init__(title=f"[b]Use Tool[/]", collapsed=True)
        self.tool_name = name
        table = Table(
            box=None,
            # title=f"[b gray50]• {name}[/]\n",
            title_style=Style(italic=False),
            title_justify="left",
            show_header=False,
            width=None,
            pad_edge=False,
            # style=Style(bgcolor="gray7")
        )
        if isinstance(input_obj, dict):
            for k, v in input_obj.items():
                table.add_row(f"[bold]{k}[/]", f"{v}")
        else:
            table.add_row("[bold]Input[/]", f"{input_obj!r}")
        self._content = Static(table)

    def compose(self):
        yield Static(Text(f"• {self.tool_name}\n", style=Style(color="gray50", bold=True)))
        yield self._content


class ToolUseApprovalBlock(Static):
    DEFAULT_CSS = """
    ListView {
        height: 6;
        margin: 1 2;
    }
    
    Label {
        margin: 1 1;
    }
    """
    def __init__(self, approval_result: asyncio.Future, tool_name, input_params):
        self._future = approval_result
        self._tool_name = tool_name
        self._input_params = input_params
        super().__init__()

    @on(ListView.Selected)
    def handle_list_view_selected(self, message: ListView.Selected):
        if message.index == 0:
            self._future.set_result(True)
        else:
            self._future.set_result(False)
        message.list_view.disabled = True


    def compose(self) -> ComposeResult:
        table = Table(
            box=None,
            title=f"[b gray50]• {self._tool_name}[/]\n",
            title_style=Style(italic=False),
            title_justify="left",
            show_header=False,
            width=None,
            pad_edge=False,
            # style=Style(bgcolor="gray7")
        )
        if isinstance(self._input_params, dict):
            for k, v in self._input_params.items():
                table.add_row(f"[bold]{k}[/]", f"{v}")
        else:
            table.add_row("[bold]Input[/]", f"{self._input_params!r}")
            
        yield Label(f"[b]• [/]Request to use tool [b]{self._tool_name}[/]")
        yield ListView(
            ListItem(Label("Accept")),
            ListItem(Label("Reject"))
        )


class ToolUseResultBlock(Static):

    def __init__(self, is_error: bool, content: Any) -> None:
        self.is_error = is_error
        self.content_text = content
        super().__init__()
    
    @staticmethod
    def _clean_text(text: str) -> str:
        """
        删除文本中 <system-reminder> ... </system-reminder> 之间的内容。
        """
        # 使用 DOTALL 模式匹配多行
        cleaned = re.sub(r"<system-reminder>.*?</system-reminder>", "", text, flags=re.DOTALL)
        return cleaned.strip()

    @staticmethod
    def _truncate_text_by_lines(text: str, max_lines: int = 5) -> str:
        """
        截断文本，仅保留前 max_lines 行，若有多余则在结尾显示:

        ```
        ... + {n} lines
        ```
        """
        lines = text.splitlines()
        if len(lines) <= max_lines:
            return text
        shown = "\n".join(lines[:max_lines])
        hidden_count = len(lines) - max_lines
        return f"{shown}\n\n... + {hidden_count} lines"

    @staticmethod
    def _truncate_text_by_count(text: str, max_count: int = 200) -> str:
        """
        截断文本，仅保留前 max_count 个字符，若有多余则在结尾显示:

        ```
        ... + {n} chars
        ```
        """
        length = len(text)
        if length <= max_count:
            return text
        shown = text[:max_count]
        hidden_count = length - max_count
        return f"{shown}\n\n... + {hidden_count} hidden"

    def _process_text(self, text: str | dict | list) -> str:
        if isinstance(text, (dict, list)):
            text = repr(text)
        text = self._clean_text(text)
        text = self._truncate_text_by_lines(text, 5)
        text = self._truncate_text_by_count(text, 200)
        return text

    def compose(self):
        if self.is_error:
            title = "[red]Error[/red]"
            collapsed = False
        else:
            title = "Tool Used"
            collapsed = True
        processed_text = self._process_text(self.content_text)
        with Collapsible(title=f"[b]{title}[/]", collapsed=collapsed):
            if self.is_error:
                result_text = Text(f"{processed_text}", style="gray50")
            else:
                result_text = Text(f"{processed_text}", style="gray50")
            yield Static(result_text)


class LogMessageBlock(Static):
    def __init__(self, message: str, level: Literal["info", "warning", "error"]):
        self.message = message
        self.level = level
        super().__init__()

    def compose(self):
        if self.level == "info":
            log_text = Text.from_markup(f"[gray50][INFO][/] {self.message}")
        elif self.level == "warning":
            log_text = Text.from_markup(f"[yellow][WARNING][/] {self.message}")
        elif self.level == "error":
            log_text = Text.from_markup(f"[bold red][ERROR][/] {self.message}")
        else:
            return
        yield Static(log_text)


class WelcomeScreen(Static):

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        super().__init__()

    def compose(self):
        info_table = Table(
            box=None,
            title_style=Style(italic=False),
            title_justify="left",
            show_header=False,
            width=None,
            pad_edge=False,
            border_style="gray50"
        )
        model = self.config["model"]["model_name"]
        base_url = self.config["model"]["base_url"]
        api_key = self.config["model"]["api_key"]
        masked_api_key = f"{api_key[:4]}****{api_key[-4:]}"
        info_table.add_row("[gray50]model:[/]", f"{model} \t[blue]/model[/] to change")
        info_table.add_row("[gray50]base_url:[/]", f"{base_url}")
        info_table.add_row("[gray50]api_key:[/]", f"{masked_api_key}")
        directory = self.config["environment"]["cwd"]
        info_table.add_row("[gray50]directory:[/]", f"{directory}")

        prompt_message = """
  [gray50]欢迎！在下方输入框中向 Tradex 发送消息开始使用，你也可以使用以下命令（命令系统暂未开放）： 

  [blue]/robot[/] - 运行机器人
  [blue]/model[/] - 切换模型
[/gray50]
"""

        content = Panel(
            Group(
                Text.from_markup("[gray50]>_ [/] Tradex\n"),
                info_table,
            )
        )
        yield Static(content)
        yield Static(Text.from_markup(prompt_message))


class MessageLog(Vertical):
    def __init__(self) -> None:
        super().__init__(id="message-log")
        self.can_focus = True
        self.auto_scroll = True

    def _scroll_to_end(self) -> None:
        self.call_after_refresh(lambda: self.scroll_end(animate=False))

    def clear(self) -> None:
        self.remove_children()
        self._scroll_to_end()

    def add_log_message(self, message: str, level: Literal["info", "warning", "error"]) -> None:
        log = LogMessageBlock(message, level)
        self.mount(log)
        if self.auto_scroll:
            self._scroll_to_end()

    def add_markdown(self, text: str) -> None:
        md = Markdown(text)
        self.mount(md)
        if self.auto_scroll:
            self._scroll_to_end()

    def add_user_message(self, text: str) -> None:
        block = MsgBlock(f"[bold]> [/]{text}", style=Style(bgcolor="gray11"), border_style="gray11")
        self.mount(block)
        if self.auto_scroll:
            self._scroll_to_end()

    def add_system_message(self, text: str) -> None:
        block = MsgBlock(f"[bold]• [/]{text}", style=Style(color="gray50"), border_style="gray7")
        self.mount(block)
        if self.auto_scroll:
            self._scroll_to_end()

    def add_tool_block(self, name: str, input_obj: Any) -> None:
        block = ToolBlock(name, input_obj)
        self.mount(block)
        if self.auto_scroll:
            self._scroll_to_end()
    
    def add_tool_result_block(self, is_error: bool, content: str):
        block = ToolUseResultBlock(is_error, content)
        self.mount(block)
        if self.auto_scroll:
            self._scroll_to_end()

    def add_tool_use_approval(self, approval_result, tool_name, input_params):
        block = ToolUseApprovalBlock(approval_result, tool_name, input_params)
        self.mount(block)
        if self.auto_scroll:
            self._scroll_to_end()
    
    def add_todo_list(self, todo_content):
        block = TodoBlock(todo_content)
        self.mount(block)
        if self.auto_scroll:
            self._scroll_to_end()

    def add_welcome_screen(self, config):
        block = WelcomeScreen(config=config)
        self.mount(block)
        if self.auto_scroll:
            self._scroll_to_end()
