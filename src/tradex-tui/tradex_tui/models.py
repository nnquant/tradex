from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Literal, Dict, Any
import time

Role = Literal["assistant", "user", "system", "tool"]

@dataclass
class Message:
    role: Role
    content: str
    meta: Dict[str, Any] = field(default_factory=dict)
    ts: float = field(default_factory=time.time)

@dataclass
class ToolUse:
    name: str
    input: Any
