"""Sandbox for bash command execution with path and command restrictions."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SandboxConfig:
    allowed_dirs: list[str] = field(default_factory=list)
    blocked_commands: list[str] = field(default_factory=lambda: [
        "rm -rf /", "mkfs", "dd if=/dev/zero", ":(){ :|:& };:",
        "shutdown", "reboot", "halt", "init 0", "init 6",
    ])
    max_output_bytes: int = 100_000
    allow_network: bool = True


class Sandbox:
    """Restricts tool execution to approved directories and commands."""

    def __init__(self, config: SandboxConfig | None = None, working_dir: str = ".") -> None:
        self.config = config or SandboxConfig()
        self.working_dir = Path(working_dir).resolve()
        if not self.config.allowed_dirs:
            self.config.allowed_dirs = [str(self.working_dir)]

    def is_path_allowed(self, path: str) -> tuple[bool, str]:
        resolved = Path(path).resolve()
        for allowed in self.config.allowed_dirs:
            allowed_path = Path(allowed).resolve()
            try:
                resolved.relative_to(allowed_path)
                return True, ""
            except ValueError:
                continue
        return False, f"Path {resolved} is outside allowed directories"

    def is_command_allowed(self, command: str) -> tuple[bool, str]:
        normalized = command.strip().lower()
        for blocked in self.config.blocked_commands:
            if blocked.lower() in normalized:
                return False, f"Blocked command pattern: {blocked}"
        return True, ""

    def prepare_env(self) -> dict[str, str]:
        """Return a sanitized environment for subprocess execution."""
        env = dict(os.environ)
        sensitive_keys = [k for k in env if any(
            s in k.upper() for s in ["SECRET", "PASSWORD", "TOKEN", "CREDENTIAL", "PRIVATE_KEY"]
        )]
        for key in sensitive_keys:
            del env[key]
        env["HOME"] = str(self.working_dir)
        return env
