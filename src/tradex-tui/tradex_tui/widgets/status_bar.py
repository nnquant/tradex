from __future__ import annotations
from textual.widgets import Static
from textual.reactive import reactive
from rich.text import Text

class StatusBar(Static):
    model = reactive("idle")
    latency_ms = reactive(None)
    tokens = reactive(None)
    tool = reactive("")
    extra = reactive("")

    def __init__(self) -> None:
        super().__init__("", id="status-bar")

    def compose_line(self) -> Text:
        t = Text()
        t.append(f" {self.model} ", style="reverse")
        if self.tool:
            t.append(f"  tool:{self.tool}", style="green")
        if self.latency_ms is not None:
            t.append(f"  {self.latency_ms}ms", style="cyan")
        if self.tokens is not None:
            t.append(f"  tok:{self.tokens}", style="magenta")
        if self.extra:
            t.append(f"  {self.extra}", style="yellow")
        return t

    def render(self) -> Text:
        return self.compose_line()
