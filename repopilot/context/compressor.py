"""Three-layer context compression pipeline.

Layer 1 - Microcompact: Truncate oversized tool outputs, keep only recent N complete results.
Layer 2 - Context Collapse: At 70% usage, fold old tool_call/tool_result pairs into summaries.
Layer 3 - Auto-compact: At 85% usage, LLM-generated structured summary of the conversation.
"""

from __future__ import annotations

import json
from typing import Any

import anthropic

from repopilot.context.token_counter import TokenCounter


SUMMARY_PROMPT = """\
Summarize the following conversation into a structured note. Preserve:
1. Key decisions made
2. Important findings (file paths, function names, patterns discovered)
3. Current task state (what's done, what's pending)
4. Any errors encountered and how they were resolved

Format as concise bullet points. Stay under 500 words.
"""


class ContextCompressor:
    """Three-layer compression pipeline for managing context window usage."""

    def __init__(
        self,
        token_counter: TokenCounter,
        context_window: int = 200_000,
        warning_threshold: float = 0.70,
        critical_threshold: float = 0.85,
        max_recent_results: int = 5,
        model: str = "claude-haiku-4-5",
    ) -> None:
        self.counter = token_counter
        self.context_window = context_window
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold
        self.max_recent_results = max_recent_results
        self.model = model
        self.client = anthropic.Anthropic()
        self._compression_count = 0

    def compress_if_needed(
        self,
        messages: list[dict[str, Any]],
        system_tokens: int,
        tool_tokens: int,
    ) -> tuple[list[dict[str, Any]], bool]:
        """Apply compression layers as needed. Returns (messages, was_compressed)."""
        available = self.context_window - system_tokens - tool_tokens
        current = self.counter.count_messages(messages)
        usage = current / available if available > 0 else 1.0

        compressed = False

        messages = self._layer1_microcompact(messages)
        current = self.counter.count_messages(messages)
        usage = current / available if available > 0 else 1.0

        if usage > self.warning_threshold:
            messages = self._layer2_context_collapse(messages)
            compressed = True
            current = self.counter.count_messages(messages)
            usage = current / available if available > 0 else 1.0

        if usage > self.critical_threshold:
            messages = self._layer3_auto_compact(messages)
            compressed = True
            self._compression_count += 1

        return messages, compressed

    def _layer1_microcompact(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Truncate oversized tool outputs; keep only recent N complete results."""
        result = []
        tool_result_indices: list[int] = []

        for i, msg in enumerate(messages):
            result.append(msg)
            if self._is_tool_result_message(msg):
                tool_result_indices.append(i)

        if len(tool_result_indices) <= self.max_recent_results:
            return result

        old_indices = set(tool_result_indices[: -self.max_recent_results])
        for i in old_indices:
            result[i] = self._truncate_tool_result(result[i])

        return result

    def _layer2_context_collapse(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Fold old tool_call + tool_result pairs into one-line summaries."""
        if len(messages) < 6:
            return messages

        boundary = len(messages) * 2 // 3
        collapsed = []
        i = 0

        while i < len(messages):
            if i >= boundary:
                collapsed.append(messages[i])
                i += 1
                continue

            msg = messages[i]
            if msg["role"] == "assistant" and self._has_tool_calls(msg):
                summary = self._summarize_tool_exchange(msg, messages[i + 1] if i + 1 < len(messages) else None)
                collapsed.append({
                    "role": "assistant",
                    "content": [{"type": "text", "text": summary}],
                })
                if i + 1 < len(messages) and self._is_tool_result_message(messages[i + 1]):
                    i += 2
                else:
                    i += 1
            else:
                collapsed.append(msg)
                i += 1

        return collapsed

    def _layer3_auto_compact(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """LLM-generated summary replaces old conversation."""
        conversation_text = self._messages_to_text(messages)

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1000,
                temperature=0.0,
                messages=[
                    {"role": "user", "content": f"{SUMMARY_PROMPT}\n\n{conversation_text}"}
                ],
            )
            summary = response.content[0].text
        except Exception:
            return messages[len(messages) // 2 :]

        summary_msg: dict[str, Any] = {
            "role": "user",
            "content": (
                f"[Context Summary - conversation compressed]\n\n{summary}\n\n"
                "Continue from where we left off."
            ),
        }
        recent = messages[len(messages) * 2 // 3 :]
        return [summary_msg] + recent

    def _truncate_tool_result(self, msg: dict[str, Any]) -> dict[str, Any]:
        content = msg.get("content")
        if isinstance(content, list):
            new_content = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    text = str(block.get("content", ""))
                    if len(text) > 200:
                        block = {
                            **block,
                            "content": text[:100] + f"\n... ({len(text)} chars, truncated) ...\n" + text[-100:],
                        }
                new_content.append(block)
            return {**msg, "content": new_content}
        if isinstance(content, str) and len(content) > 500:
            return {**msg, "content": content[:200] + "\n... (truncated) ...\n" + content[-200:]}
        return msg

    def _is_tool_result_message(self, msg: dict[str, Any]) -> bool:
        content = msg.get("content")
        if isinstance(content, list):
            return any(
                isinstance(b, dict) and b.get("type") == "tool_result" for b in content
            )
        return False

    def _has_tool_calls(self, msg: dict[str, Any]) -> bool:
        content = msg.get("content")
        if isinstance(content, list):
            return any(
                isinstance(b, dict) and b.get("type") == "tool_use" for b in content
            )
        return False

    def _summarize_tool_exchange(
        self, assistant_msg: dict[str, Any], result_msg: dict[str, Any] | None
    ) -> str:
        calls = []
        content = assistant_msg.get("content", [])
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "tool_use":
                        calls.append(f"{block['name']}({json.dumps(block.get('input', {}))[:60]})")
                    elif block.get("type") == "text":
                        calls.append(block["text"][:100])

        summary = f"[Collapsed] Called: {', '.join(calls)}"

        if result_msg:
            result_content = result_msg.get("content")
            if isinstance(result_content, list):
                for block in result_content:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        result_text = str(block.get("content", ""))[:100]
                        summary += f" → {result_text}"
                        break

        return summary

    def _messages_to_text(self, messages: list[dict[str, Any]]) -> str:
        parts = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if isinstance(content, str):
                parts.append(f"{role}: {content[:500]}")
            elif isinstance(content, list):
                texts = []
                for block in content:
                    if isinstance(block, dict):
                        if block.get("type") == "text":
                            texts.append(block["text"][:200])
                        elif block.get("type") == "tool_use":
                            texts.append(f"[tool:{block['name']}]")
                        elif block.get("type") == "tool_result":
                            texts.append(f"[result:{str(block.get('content', ''))[:100]}]")
                parts.append(f"{role}: {' | '.join(texts)}")
        return "\n".join(parts[-30:])

    @property
    def compression_count(self) -> int:
        return self._compression_count
