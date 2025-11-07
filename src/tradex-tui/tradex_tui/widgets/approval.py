from __future__ import annotations
from textual.widgets import Button, Input, Label
from textual.containers import Horizontal, Vertical, Center
from textual.screen import ModalScreen
from dataclasses import dataclass

@dataclass
class ApprovalResult:
    approved: bool
    reason: str

class ApprovalModal(ModalScreen[ApprovalResult]):
    def __init__(self, title: str, detail: str, require_reason: bool = False) -> None:
        super().__init__()
        self.title = title
        self.detail = detail
        self.require_reason = require_reason

    def compose(self):
        yield Center(Vertical(
            Label(self.title, id="approval-title"),
            Label(str(self.detail), id="approval-detail"),
            Input(placeholder="optional reason..." if not self.require_reason else "reason required...", id="reason"),
            Horizontal(
                Button("Approve", id="approve", variant="success"),
                Button("Reject", id="reject", variant="error"),
                id="approval-buttons"
            ),
            id="approval-wrap"
        ))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "approve":
            self.dismiss(ApprovalResult(True, self.query_one("#reason", Input).value or ""))
        elif event.button.id == "reject":
            self.dismiss(ApprovalResult(False, self.query_one("#reason", Input).value or ""))
