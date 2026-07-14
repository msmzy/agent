"""Base class for all tools and tool result container."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolResult:
    output: str = ""
    error: str = ""
    is_error: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_api_format(self) -> dict[str, Any]:
        if self.is_error:
            return {"type": "text", "text": f"Error: {self.error}"}
        return {"type": "text", "text": self.output}


class BaseTool(ABC):
    name: str
    description: str

    @abstractmethod
    def get_input_schema(self) -> dict[str, Any]:
        ...

    @abstractmethod
    def execute(self, **kwargs: Any) -> ToolResult:
        ...

    @property
    def risk_level(self) -> str:
        """Tool risk classification: read_only / write / dangerous."""
        return "read_only"

    def to_api_format(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.get_input_schema(),
        }
