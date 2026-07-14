"""Bootstrap: wire all components together into a working agent."""

from __future__ import annotations

from pathlib import Path

from repopilot.agent.loop import AgentLoop
from repopilot.config.settings import Settings, load_settings
from repopilot.permissions.checker import PermissionChecker
from repopilot.permissions.rules import RuleEngine
from repopilot.permissions.security import SecurityReviewer
from repopilot.tools.bash import BashTool
from repopilot.tools.edit_file import EditFileTool
from repopilot.tools.glob_tool import GlobTool
from repopilot.tools.grep_tool import GrepTool
from repopilot.tools.read_file import ReadFileTool
from repopilot.tools.registry import ToolRegistry
from repopilot.tools.write_file import WriteFileTool

SYSTEM_PROMPT = """\
You are RepoPilot, an AI coding agent. You help users with software engineering tasks \
by reading, writing, and editing code files, searching codebases, and executing commands.

## Core Principles
- Be concise and direct in responses
- Prefer editing existing files over creating new ones
- Never introduce security vulnerabilities
- Ask for confirmation before destructive operations
- Use tools to accomplish tasks, don't just describe what to do

## Available Capabilities
- Read, write, and edit files
- Search files by name (glob) or content (grep)
- Execute bash commands
- Spawn sub-agents for complex parallel tasks
- Load skills for specialized workflows

## Working Directory
You are working in: {working_dir}

## Project Context
{project_context}
"""


def create_agent_loop(
    model: str = "claude-sonnet-4-6",
    working_dir: str = ".",
    permission_mode: str = "default",
) -> AgentLoop:
    working_path = Path(working_dir).resolve()
    settings = load_settings(working_path)
    settings = settings.merge({"model": model, "permission_mode": permission_mode})

    registry = _build_tool_registry()

    rule_engine = RuleEngine.from_settings(settings)
    security = SecurityReviewer()
    perm_checker = PermissionChecker(
        rule_engine=rule_engine,
        security_reviewer=security,
        permission_mode=settings.permission_mode,
    )

    project_context = _load_project_context(working_path)
    system = SYSTEM_PROMPT.format(
        working_dir=str(working_path),
        project_context=project_context,
    )

    loop = AgentLoop(
        settings=settings,
        tool_registry=registry,
        system_prompt=system,
        permission_checker=perm_checker.check,
    )

    return loop


def _build_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    for tool_cls in [ReadFileTool, WriteFileTool, EditFileTool, GlobTool, GrepTool, BashTool]:
        registry.register(tool_cls())
    return registry


def _load_project_context(working_dir: Path) -> str:
    """Load REPOPILOT.md or README.md as project context."""
    for name in ["REPOPILOT.md", ".repopilot/REPOPILOT.md", "README.md"]:
        path = working_dir / name
        if path.exists():
            content = path.read_text(encoding="utf-8", errors="replace")
            if len(content) > 4000:
                content = content[:4000] + "\n\n... (truncated)"
            return content
    return "(No project documentation found)"
