"""Permission checker integrating rule engine, security review, and user confirmation."""

from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm

from repopilot.permissions.rules import RiskLevel, RuleEngine, TOOL_RISK_MAP
from repopilot.permissions.security import SecurityReviewer

console = Console()


class PermissionChecker:
    """Multi-layer permission check:
    1. Rule engine (deny-first)
    2. Bash command security scan
    3. Prompt injection detection
    4. User confirmation for unresolved cases
    """

    def __init__(
        self,
        rule_engine: RuleEngine,
        security_reviewer: SecurityReviewer | None = None,
        auto_approve_reads: bool = True,
        permission_mode: str = "default",
    ) -> None:
        self.rule_engine = rule_engine
        self.security = security_reviewer or SecurityReviewer()
        self.auto_approve_reads = auto_approve_reads
        self.permission_mode = permission_mode
        self._session_approvals: set[str] = set()

    def check(self, tool_name: str, tool_input: dict[str, Any]) -> bool:
        if self.permission_mode == "plan":
            risk = TOOL_RISK_MAP.get(tool_name, RiskLevel.DANGEROUS)
            if risk != RiskLevel.READ_ONLY:
                console.print(f"[yellow]Plan mode: blocked write/dangerous tool '{tool_name}'[/yellow]")
                return False

        allowed, reason = self.rule_engine.evaluate(tool_name, tool_input)
        if allowed:
            return True

        if tool_name == "bash":
            command = tool_input.get("command", "")
            safe, bash_reason = self.rule_engine.check_bash_command(command)
            if not safe:
                console.print(Panel(
                    f"[red]Blocked:[/red] {bash_reason}\n[dim]Command: {command}[/dim]",
                    title="Security Alert",
                    border_style="red",
                ))
                return False

        injection_result = self.security.check_tool_input(tool_name, tool_input)
        if injection_result.is_suspicious:
            console.print(Panel(
                f"[red]Suspicious input detected:[/red]\n{injection_result.reason}",
                title="Security Warning",
                border_style="red",
            ))
            if injection_result.severity == "high":
                return False

        approval_key = f"{tool_name}:{_hash_input(tool_input)}"
        if approval_key in self._session_approvals:
            return True

        return self._ask_user(tool_name, tool_input, reason, approval_key)

    def _ask_user(
        self, tool_name: str, tool_input: dict[str, Any], reason: str, approval_key: str
    ) -> bool:
        console.print(Panel(
            f"[yellow]Tool:[/yellow] {tool_name}\n"
            f"[yellow]Input:[/yellow] {_format_input(tool_input)}\n"
            f"[dim]Reason: {reason}[/dim]",
            title="Permission Required",
            border_style="yellow",
        ))

        try:
            approved = Confirm.ask("Allow this action?", default=False)
        except (EOFError, KeyboardInterrupt):
            return False

        if approved:
            self._session_approvals.add(approval_key)

        return approved


def _hash_input(tool_input: dict[str, Any]) -> str:
    import hashlib
    return hashlib.md5(str(sorted(tool_input.items())).encode()).hexdigest()[:8]


def _format_input(tool_input: dict[str, Any]) -> str:
    parts = []
    for k, v in tool_input.items():
        val = str(v)
        if len(val) > 200:
            val = val[:197] + "..."
        parts.append(f"  {k}: {val}")
    return "\n".join(parts)
