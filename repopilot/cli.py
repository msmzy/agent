"""CLI entry point using Typer."""

from __future__ import annotations

from pathlib import Path

import typer

from repopilot import __version__
from repopilot.output import safe_print

app = typer.Typer(
    name="repopilot",
    help="RepoPilot - AI Coding Agent",
    no_args_is_help=True,
)


@app.command()
def chat(
    model: str = typer.Option("claude-sonnet-4-6", "--model", "-m", help="Model to use"),
    working_dir: str = typer.Option(".", "--dir", "-d", help="Working directory"),
    permission_mode: str = typer.Option(
        "default", "--permission-mode", "-p",
        help="Permission mode: default, auto-edit, plan",
    ),
) -> None:
    """Start an interactive REPL session."""
    from repopilot.repl import start_repl
    start_repl(model=model, working_dir=working_dir, permission_mode=permission_mode)


@app.command()
def run(
    task: str = typer.Argument(help="Task to execute"),
    model: str = typer.Option("claude-sonnet-4-6", "--model", "-m"),
    working_dir: str = typer.Option(".", "--dir", "-d"),
) -> None:
    """Execute a single task and exit."""
    from repopilot.runner import run_task
    result = run_task(task=task, model=model, working_dir=working_dir)
    safe_print(result)


@app.command()
def version() -> None:
    """Show version information."""
    safe_print(f"RepoPilot v{__version__}")


@app.command()
def init(
    working_dir: str = typer.Option(".", "--dir", "-d"),
) -> None:
    """Initialize RepoPilot config in the current project."""
    config_dir = Path(working_dir) / ".repopilot"
    config_dir.mkdir(exist_ok=True)
    (config_dir / "memory").mkdir(exist_ok=True)
    (config_dir / "skills").mkdir(exist_ok=True)

    settings_file = config_dir / "settings.json"
    if not settings_file.exists():
        settings_file.write_text('{\n  "model": "claude-sonnet-4-6",\n  "max_tokens": 8192\n}\n')

    memory_index = config_dir / "memory" / "MEMORY.md"
    if not memory_index.exists():
        memory_index.write_text("# RepoPilot Memory Index\n")

    safe_print(f"Initialized RepoPilot in {config_dir}")


if __name__ == "__main__":
    app()
