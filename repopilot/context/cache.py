"""Prompt cache optimization: manage cache_control breakpoints for maximum reuse.

Strategy: system prompt + tool definitions are the most stable prefix.
Keep their ordering deterministic to maximize cache hit rate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CacheStats:
    total_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0

    @property
    def hit_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.cache_hits / self.total_requests

    def summary(self) -> str:
        return (
            f"Cache stats: {self.total_requests} requests, "
            f"{self.hit_rate:.1%} hit rate, "
            f"{self.cache_read_tokens:,} read tokens, "
            f"{self.cache_creation_tokens:,} creation tokens"
        )


class CacheManager:
    """Manages prompt cache breakpoints for the Anthropic API.

    Cache works by prefix matching on KV cache tensors.
    Ordering: system prompt (most stable) → tool definitions (stable per session)
    → conversation history → new message.
    """

    def __init__(self) -> None:
        self.stats = CacheStats()

    def prepare_system_blocks(self, system_prompt: str) -> list[dict[str, Any]]:
        """Wrap system prompt with cache_control for prefix caching."""
        return [
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ]

    def prepare_tools(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Add cache_control to the last tool definition to cache the entire tool block."""
        if not tools:
            return tools
        prepared = [dict(t) for t in tools]
        prepared[-1] = {**prepared[-1], "cache_control": {"type": "ephemeral"}}
        return prepared

    def prepare_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Optionally add cache breakpoints to conversation history.

        Add a breakpoint every N turns to enable partial cache reuse
        when new messages are appended.
        """
        if len(messages) < 4:
            return messages

        prepared = [dict(m) for m in messages]
        breakpoint_interval = max(4, len(prepared) // 3)

        breakpoints_placed = 0
        for i in range(breakpoint_interval - 1, len(prepared) - 1, breakpoint_interval):
            if breakpoints_placed >= 2:
                break
            msg = prepared[i]
            content = msg.get("content")
            if isinstance(content, str):
                prepared[i] = {
                    **msg,
                    "content": [
                        {
                            "type": "text",
                            "text": content,
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                }
                breakpoints_placed += 1

        return prepared

    def update_stats(self, usage: Any) -> None:
        """Update cache statistics from API response usage."""
        self.stats.total_requests += 1
        read_tokens = getattr(usage, "cache_read_input_tokens", 0)
        creation_tokens = getattr(usage, "cache_creation_input_tokens", 0)
        self.stats.cache_read_tokens += read_tokens
        self.stats.cache_creation_tokens += creation_tokens
        if read_tokens > 0:
            self.stats.cache_hits += 1
        else:
            self.stats.cache_misses += 1
