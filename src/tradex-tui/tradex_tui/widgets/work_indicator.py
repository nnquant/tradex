from __future__ import annotations

from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static


class WorkIndicator(Static):
    """
    显示 Agent 是否正在执行任务的指示条。

    :param message: 初始提示文案。
    :type message: str
    """

    DEFAULT_CSS = """
    WorkIndicator {
        margin: 1 1;
        color: gray;
        content-align: left middle;
    }
    """

    message: reactive[str] = reactive("任务正在进行，请稍候...")
    is_working: reactive[bool] = reactive(False)

    def __init__(self) -> None:
        super().__init__("", id="work-indicator")
        self._apply_visibility()

    def on_mount(self):
        def animate_loop():
            target_opacity = 1 if self.styles.opacity == 0.5 else 0.5
            self.styles.animate("opacity", value=target_opacity, duration=1, on_complete=animate_loop)
        self.styles.animate("opacity", value=0.5, duration=1, on_complete=animate_loop, easing="in_out_expo")
    

    def show_progress(self, message: str | None = None) -> None:
        """
        显示指示条并更新提示文案。

        :param message: 待展示的提示内容。
        :type message: str | None
        """

        if message:
            self.message = message
        self.is_working = True
        self._apply_visibility()

    def hide(self) -> None:
        """隐藏指示条。"""

        self.is_working = False
        self._apply_visibility()

    def _apply_visibility(self) -> None:
        if self.is_working:
            self.styles.height = None
            self.styles.padding = (0, 2)
        else:
            self.styles.height = 0
            self.styles.padding = 0

    def render(self) -> Text:
        if not self.is_working:
            return Text("")
        return Text(f"{self.message}")
