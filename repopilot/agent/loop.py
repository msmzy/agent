"""Core Query Loop: the while(tool_call) agent execution engine."""

from __future__ import annotations

from typing import Any, Callable

import anthropic

from repopilot.agent.messages import Conversation, ToolResultMsg
from repopilot.config.settings import Settings
from repopilot.output import safe_print, print_tool_call, print_error, print_dim
from repopilot.tools.base import ToolResult
from repopilot.tools.registry import ToolRegistry


class AgentLoop:
    """Implements the Query Loop pattern:
    1. Assemble context (system prompt + tools + history)
    2. Call Claude API (streaming)
    3. If stop_reason == "tool_use": execute tools, append results, loop
    4. If stop_reason == "end_turn": return final response
    """

    def __init__(
        self,
        settings: Settings,
        tool_registry: ToolRegistry,
        system_prompt: str,
        permission_checker: Callable[..., bool] | None = None,
        on_context_check: Callable[[Conversation], Conversation] | None = None,
    ) -> None:
        self.settings = settings
        self.registry = tool_registry
        self.system_prompt = system_prompt
        self.permission_checker = permission_checker
        self.on_context_check = on_context_check
        self.conversation = Conversation(system_prompt=system_prompt)
        self.client = anthropic.Anthropic()
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.cache_read_tokens = 0
        self.cache_creation_tokens = 0

    def run(self, user_message: str) -> str:
        self.conversation.add_user(user_message)
        return self._loop()

    def _loop(self) -> str:
        iteration = 0

        while iteration < self.settings.max_iterations:
            iteration += 1

            if self.on_context_check:
                self.conversation = self.on_context_check(self.conversation)

            response = self._call_api()
            self._track_usage(response.usage)

            assistant_content = self._extract_content(response)
            self.conversation.add_assistant(assistant_content)

            if response.stop_reason == "end_turn":
                return self._extract_text(assistant_content)

            if response.stop_reason == "tool_use":
                tool_results = self._execute_tools(assistant_content)
                self.conversation.add_tool_results(tool_results)
                continue

            return self._extract_text(assistant_content)

        return "[RepoPilot] Maximum iterations reached."

    def _call_api(self) -> Any:
        system_blocks = [
            {
                "type": "text",
                "text": self.system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ]

        tools = self.registry.to_api_format()
        if tools:
            tools[-1]["cache_control"] = {"type": "ephemeral"}

        return self.client.messages.create(
            model=self.settings.model,
            max_tokens=self.settings.max_tokens,
            temperature=self.settings.temperature,
            system=system_blocks,
            tools=tools,
            messages=self.conversation.to_api_messages(),
        )

    def _extract_content(self, response: Any) -> list[dict[str, Any]]:
        content = []
        for block in response.content:
            if block.type == "text":
                content.append({"type": "text", "text": block.text})
                safe_print(block.text)
            elif block.type == "tool_use":
                content.append({
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })
        return content

    def _extract_text(self, content: list[dict[str, Any]]) -> str:
        texts = [b["text"] for b in content if b.get("type") == "text"]
        return "\n".join(texts)

    def _execute_tools(self, content: list[dict[str, Any]]) -> list[ToolResultMsg]:
        results = []
        tool_calls = [b for b in content if b.get("type") == "tool_use"]

        for call in tool_calls:
            tool_name = call["name"]
            tool_id = call["id"]
            tool_input = call.get("input", {})

            if self.permission_checker and not self.permission_checker(tool_name, tool_input):
                results.append(ToolResultMsg(
                    tool_use_id=tool_id,
                    content="Permission denied: this action requires user approval.",
                    is_error=True,
                ))
                continue

            print_tool_call(tool_name, _format_args(tool_input))

            tool_result: ToolResult = self.registry.execute(tool_name, **tool_input)

            if tool_result.is_error:
                print_error(tool_result.error)
            elif tool_result.output:
                preview = tool_result.output[:500]
                if len(tool_result.output) > 500:
                    preview += "..."
                print_dim(preview)

            results.append(ToolResultMsg(
                tool_use_id=tool_id,
                content=tool_result.error if tool_result.is_error else tool_result.output,
                is_error=tool_result.is_error,
            ))

        return results

    def _track_usage(self, usage: Any) -> None:
        self.total_input_tokens += getattr(usage, "input_tokens", 0)
        self.total_output_tokens += getattr(usage, "output_tokens", 0)
        self.cache_read_tokens += getattr(usage, "cache_read_input_tokens", 0)
        self.cache_creation_tokens += getattr(usage, "cache_creation_input_tokens", 0)

    def get_usage_summary(self) -> dict[str, int]:
        return {
            "input_tokens": self.total_input_tokens,
            "output_tokens": self.total_output_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "cache_creation_tokens": self.cache_creation_tokens,
        }


def _format_args(args: dict[str, Any]) -> str:
    parts = []
    for k, v in args.items():
        val = repr(v)
        if len(val) > 80:
            val = val[:77] + "..."
        parts.append(f"{k}={val}")
    return ", ".join(parts)
