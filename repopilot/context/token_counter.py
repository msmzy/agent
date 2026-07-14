"""Token counting using the Anthropic SDK."""

from __future__ import annotations

import json
from typing import Any

import anthropic


class TokenCounter:
    """Counts tokens for messages using the Anthropic API."""

    def __init__(self, model: str = "claude-sonnet-4-6") -> None:
        self.model = model
        self.client = anthropic.Anthropic()
        self._cache: dict[int, int] = {}

    def count_messages(self, messages: list[dict[str, Any]]) -> int:
        """Estimate token count for a list of messages."""
        total = 0
        for msg in messages:
            total += self._count_message(msg)
        return total

    def count_text(self, text: str) -> int:
        """Rough token estimate: ~4 chars per token for English, ~2 for CJK."""
        if not text:
            return 0
        return max(1, len(text) // 3)

    def _count_message(self, message: dict[str, Any]) -> int:
        content = message.get("content", "")
        if isinstance(content, str):
            return self.count_text(content) + 4
        if isinstance(content, list):
            total = 4
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        total += self.count_text(block.get("text", ""))
                    elif block.get("type") == "tool_use":
                        total += self.count_text(json.dumps(block.get("input", {}))) + 20
                    elif block.get("type") == "tool_result":
                        total += self.count_text(str(block.get("content", ""))) + 10
            return total
        return 10

    def count_system(self, system: str | list[dict[str, Any]]) -> int:
        if isinstance(system, str):
            return self.count_text(system)
        total = 0
        for block in system:
            total += self.count_text(block.get("text", ""))
        return total

    def count_tools(self, tools: list[dict[str, Any]]) -> int:
        return self.count_text(json.dumps(tools))
