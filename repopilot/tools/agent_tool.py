"""Agent tool: spawns sub-agents as tool calls for parallel task execution.

Central orchestration pattern: the main agent dispatches tasks to sub-agents
via tool_call, sub-agents execute with restricted tool sets and path boundaries,
results return as tool_results. No control transfer.
"""

from __future__ import annotations

from typing import Any

from repopilot.tools.base import BaseTool, ToolResult


class AgentTool(BaseTool):
    """Spawns a sub-agent to handle a delegated task."""

    name = "agent"
    description = (
        "Spawn a sub-agent to handle a complex or independent task. "
        "Sub-agents have their own context window and restricted tool access. "
        "Use for parallel work, exploration, or tasks that need isolation."
    )

    def __init__(self, sub_agent_manager: Any) -> None:
        self.manager = sub_agent_manager

    @property
    def risk_level(self) -> str:
        return "write"

    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": "Short description of the sub-agent task (3-5 words).",
                },
                "prompt": {
                    "type": "string",
                    "description": "Detailed task prompt for the sub-agent.",
                },
                "agent_type": {
                    "type": "string",
                    "enum": ["explore", "plan", "general"],
                    "description": "Type of sub-agent to spawn.",
                    "default": "general",
                },
                "allowed_tools": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tool names the sub-agent can use. Defaults to read-only tools.",
                },
            },
            "required": ["description", "prompt"],
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        description = kwargs.get("description", "")
        prompt = kwargs.get("prompt", "")
        agent_type = kwargs.get("agent_type", "general")
        allowed_tools = kwargs.get("allowed_tools")

        if not prompt:
            return ToolResult(error="Sub-agent prompt is required", is_error=True)

        try:
            result = self.manager.spawn_and_run(
                description=description,
                prompt=prompt,
                agent_type=agent_type,
                allowed_tools=allowed_tools,
            )
            return ToolResult(
                output=result,
                metadata={"agent_type": agent_type, "description": description},
            )
        except Exception as e:
            return ToolResult(error=f"Sub-agent failed: {e}", is_error=True)
