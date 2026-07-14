"""Single-task runner for non-interactive mode."""

from __future__ import annotations

from repopilot.bootstrap import create_agent_loop


def run_task(task: str, model: str = "claude-sonnet-4-6", working_dir: str = ".") -> str:
    loop = create_agent_loop(model=model, working_dir=working_dir)
    return loop.run(task)
