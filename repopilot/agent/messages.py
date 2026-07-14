"""Message types and conversation history management."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    id: str
    name: str
    input: dict[str, Any]


@dataclass
class ToolResultMsg:
    tool_use_id: str
    content: str
    is_error: bool = False


@dataclass
class Conversation:
    """Manages conversation history in Claude API format."""

    messages: list[dict[str, Any]] = field(default_factory=list)
    system_prompt: str = ""

    def add_user(self, text: str) -> None:
        self.messages.append({"role": "user", "content": text})

    def add_assistant(self, content: list[dict[str, Any]]) -> None:
        self.messages.append({"role": "assistant", "content": content})

    def add_tool_results(self, results: list[ToolResultMsg]) -> None:
        content = []
        for r in results:
            block: dict[str, Any] = {
                "type": "tool_result",
                "tool_use_id": r.tool_use_id,
                "content": r.content,
            }
            if r.is_error:
                block["is_error"] = True
            content.append(block)
        self.messages.append({"role": "user", "content": content})

    def to_api_messages(self) -> list[dict[str, Any]]:
        return list(self.messages)

    @property
    def turn_count(self) -> int:
        return sum(1 for m in self.messages if m["role"] == "user" and isinstance(m["content"], str))

    def get_last_assistant_text(self) -> str:
        for msg in reversed(self.messages):
            if msg["role"] == "assistant":
                content = msg["content"]
                if isinstance(content, str):
                    return content
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        return block.get("text", "")
        return ""
