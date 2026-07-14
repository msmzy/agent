"""Interactive REPL using prompt-toolkit and Rich."""

from __future__ import annotations

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

from repopilot import __version__
from repopilot.bootstrap import create_agent_loop

console = Console()

SLASH_COMMANDS = {
    "/help": "Show available commands",
    "/clear": "Clear conversation history",
    "/usage": "Show token usage statistics",
    "/mode": "Switch permission mode (default/auto-edit/plan)",
    "/memory": "Show loaded memories",
    "/skills": "List available skills",
    "/exit": "Exit RepoPilot",
}


def start_repl(
    model: str = "claude-sonnet-4-6",
    working_dir: str = ".",
    permission_mode: str = "default",
) -> None:
    _print_banner()

    loop = create_agent_loop(
        model=model,
        working_dir=working_dir,
        permission_mode=permission_mode,
    )

    history_file = _get_history_path()
    session: PromptSession[str] = PromptSession(
        history=FileHistory(str(history_file)),
        auto_suggest=AutoSuggestFromHistory(),
    )

    while True:
        try:
            user_input = session.prompt("\n❯ ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Goodbye![/dim]")
            break

        if not user_input:
            continue

        if user_input.startswith("/"):
            handled = _handle_slash_command(user_input, loop)
            if handled == "exit":
                break
            continue

        try:
            loop.run(user_input)
        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted[/yellow]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


def _print_banner() -> None:
    console.print(Panel(
        f"[bold cyan]RepoPilot[/bold cyan] v{__version__}\n"
        "[dim]AI Coding Agent | Type /help for commands[/dim]",
        border_style="cyan",
    ))


def _handle_slash_command(cmd: str, loop: object) -> str | None:
    parts = cmd.split(maxsplit=1)
    command = parts[0].lower()

    if command == "/exit" or command == "/quit":
        console.print("[dim]Goodbye![/dim]")
        return "exit"

    if command == "/help":
        rows = [f"  [cyan]{k}[/cyan]  {v}" for k, v in SLASH_COMMANDS.items()]
        console.print(Panel("\n".join(rows), title="Commands", border_style="cyan"))
        return None

    if command == "/clear":
        from repopilot.agent.messages import Conversation
        if hasattr(loop, "conversation"):
            loop.conversation = Conversation(system_prompt=loop.conversation.system_prompt)  # type: ignore[attr-defined]
        console.print("[dim]Conversation cleared.[/dim]")
        return None

    if command == "/usage":
        if hasattr(loop, "get_usage_summary"):
            usage = loop.get_usage_summary()  # type: ignore[attr-defined]
            lines = [f"  {k}: {v:,}" for k, v in usage.items()]
            console.print(Panel("\n".join(lines), title="Token Usage", border_style="green"))
        return None

    if command == "/mode":
        if len(parts) > 1 and hasattr(loop, "permission_checker"):
            mode = parts[1]
            if mode in ("default", "auto-edit", "plan"):
                loop.permission_checker.permission_mode = mode  # type: ignore[attr-defined]
                console.print(f"[green]Permission mode: {mode}[/green]")
            else:
                console.print("[red]Valid modes: default, auto-edit, plan[/red]")
        return None

    if command == "/memory":
        if hasattr(loop, "memory_store"):
            memories = loop.memory_store.list_all()  # type: ignore[attr-defined]
            if memories:
                for m in memories:
                    console.print(f"  [{m.type}] {m.name}: {m.description}")
            else:
                console.print("[dim]No memories stored.[/dim]")
        return None

    if command == "/skills":
        if hasattr(loop, "skill_loader"):
            skills = loop.skill_loader.list_skills()  # type: ignore[attr-defined]
            if skills:
                for s in skills:
                    console.print(f"  [cyan]{s.name}[/cyan]: {s.description}")
            else:
                console.print("[dim]No skills loaded.[/dim]")
        return None

    console.print(f"[yellow]Unknown command: {command}[/yellow]")
    return None


def _get_history_path():
    from pathlib import Path
    history_dir = Path.home() / ".repopilot"
    history_dir.mkdir(exist_ok=True)
    return history_dir / "history.txt"
