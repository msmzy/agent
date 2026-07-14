"""Memory types and record model."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class MemoryType(str, Enum):
    USER = "user"
    FEEDBACK = "feedback"
    PROJECT = "project"
    REFERENCE = "reference"
    PROCEDURAL = "procedural"


@dataclass
class MemoryRecord:
    name: str
    description: str
    type: MemoryType
    content: str
    file_path: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    access_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def filename(self) -> str:
        safe_name = self.name.lower().replace(" ", "_")
        safe_name = "".join(c for c in safe_name if c.isalnum() or c == "_")
        return f"{self.type.value}_{safe_name}.md"

    def to_frontmatter(self) -> str:
        lines = [
            "---",
            f"name: {self.name}",
            f"description: {self.description}",
            f"type: {self.type.value}",
            f"created_at: {self.created_at}",
            f"updated_at: {self.updated_at}",
            f"access_count: {self.access_count}",
            "---",
            "",
            self.content,
        ]
        return "\n".join(lines)

    def index_entry(self) -> str:
        return f"- [{self.name}]({self.filename}) — {self.description}"
