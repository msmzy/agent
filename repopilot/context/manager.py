"""Context manager: monitors token usage, triggers compression, re-injects stable context."""

from __future__ import annotations

from typing import Any

from repopilot.agent.messages import Conversation
from repopilot.context.cache import CacheManager
from repopilot.context.compressor import ContextCompressor
from repopilot.context.token_counter import TokenCounter


class ContextManager:
    """Orchestrates context window management.

    Monitors token usage and triggers compression when thresholds are reached.
    Ensures system prompt, tool definitions, and project context survive compression.
    """

    def __init__(
        self,
        system_prompt: str,
        tools: list[dict[str, Any]],
        context_window: int = 200_000,
        warning_threshold: float = 0.70,
        critical_threshold: float = 0.85,
        model: str = "claude-sonnet-4-6",
    ) -> None:
        self.system_prompt = system_prompt
        self.tools = tools
        self.counter = TokenCounter(model=model)
        self.cache_manager = CacheManager()
        self.compressor = ContextCompressor(
            token_counter=self.counter,
            context_window=context_window,
            warning_threshold=warning_threshold,
            critical_threshold=critical_threshold,
            model="claude-haiku-4-5",
        )

        self._system_tokens = self.counter.count_text(system_prompt)
        self._tool_tokens = self.counter.count_tools(tools)

    def check_and_compress(self, conversation: Conversation) -> Conversation:
        """Check context usage and compress if needed."""
        messages, was_compressed = self.compressor.compress_if_needed(
            messages=conversation.to_api_messages(),
            system_tokens=self._system_tokens,
            tool_tokens=self._tool_tokens,
        )

        if was_compressed:
            conversation.messages = messages

        return conversation

    def get_usage_report(self, conversation: Conversation) -> dict[str, Any]:
        msg_tokens = self.counter.count_messages(conversation.to_api_messages())
        total = self._system_tokens + self._tool_tokens + msg_tokens
        usage_pct = total / self.compressor.context_window

        return {
            "system_tokens": self._system_tokens,
            "tool_tokens": self._tool_tokens,
            "message_tokens": msg_tokens,
            "total_tokens": total,
            "context_window": self.compressor.context_window,
            "usage_percent": f"{usage_pct:.1%}",
            "compressions_triggered": self.compressor.compression_count,
            "cache_stats": self.cache_manager.stats.summary(),
        }

    def prepare_api_request(
        self, conversation: Conversation
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        """Prepare system, tools, and messages with cache breakpoints."""
        system = self.cache_manager.prepare_system_blocks(self.system_prompt)
        tools = self.cache_manager.prepare_tools(self.tools)
        messages = self.cache_manager.prepare_messages(conversation.to_api_messages())
        return system, tools, messages
