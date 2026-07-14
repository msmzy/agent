"""Safe output utilities for Windows CJK/emoji compatibility."""

from __future__ import annotations

import os
import sys

from rich.console import Console
from rich.panel import Panel


def _init_windows_utf8() -> None:
    """Set Windows console to UTF-8 mode."""
    if sys.platform == "win32":
        os.system("chcp 65001 > nul 2>&1")


_init_windows_utf8()

console = Console(highlight=False)


def safe_print(text: str) -> None:
    try:
        sys.stdout.buffer.write(text.encode("utf-8", errors="replace"))
        sys.stdout.buffer.write(b"\n")
        sys.stdout.buffer.flush()
    except Exception:
        print(text.encode("ascii", errors="replace").decode())


def print_panel(content: str, title: str = "", border_style: str = "cyan") -> None:
    try:
        console.print(Panel(content, title=title, border_style=border_style))
    except (UnicodeEncodeError, OSError):
        safe_print(f"[{title}] {content}")


def print_tool_call(name: str, args_str: str) -> None:
    try:
        console.print(Panel(
            f"[bold]{name}[/bold]({args_str})",
            title="Tool Call",
            border_style="cyan",
        ))
    except (UnicodeEncodeError, OSError):
        safe_print(f"[Tool Call] {name}({args_str})")


def print_error(msg: str) -> None:
    try:
        console.print(f"[red]Error:[/red] {msg}")
    except (UnicodeEncodeError, OSError):
        safe_print(f"Error: {msg}")


def print_dim(msg: str) -> None:
    try:
        console.print(f"[dim]{msg}[/dim]")
    except (UnicodeEncodeError, OSError):
        safe_print(msg)
