"""Wraps the Skill system as a Tool callable by the agent."""

from __future__ import annotations

from typing import Any

from repopilot.skills.loader import SkillLoader
from repopilot.skills.router import SkillRouter
from repopilot.tools.base import BaseTool, ToolResult


class SkillTool(BaseTool):
    """Exposes skills as a meta-tool. When invoked, loads the full skill body
    into context and returns it as instructions for the agent to follow."""

    name = "skill"
    description = (
        "Invoke a skill by name. Skills are specialized capabilities for "
        "common workflows like code review, initialization, etc."
    )

    def __init__(self, loader: SkillLoader, router: SkillRouter) -> None:
        self.loader = loader
        self.router = router

    def get_input_schema(self) -> dict[str, Any]:
        skills = self.loader.list_skills()
        skill_names = [s.name for s in skills]
        return {
            "type": "object",
            "properties": {
                "skill": {
                    "type": "string",
                    "description": f"Skill name to invoke. Available: {', '.join(skill_names)}",
                },
                "args": {
                    "type": "string",
                    "description": "Optional arguments for the skill.",
                },
            },
            "required": ["skill"],
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        skill_name = kwargs.get("skill", "")
        args = kwargs.get("args", "")

        body = self.loader.load_body(skill_name)
        if body is None:
            available = [s.name for s in self.loader.list_skills()]
            return ToolResult(
                error=f"Skill '{skill_name}' not found. Available: {', '.join(available)}",
                is_error=True,
            )

        output = f"<skill-instructions name=\"{skill_name}\">\n{body}\n</skill-instructions>"
        if args:
            output += f"\n\nUser arguments: {args}"

        return ToolResult(output=output, metadata={"skill": skill_name})
