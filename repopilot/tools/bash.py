"""Bash command execution tool with timeout and output capture."""

from __future__ import annotations

import subprocess
from typing import Any

from repopilot.tools.base import BaseTool, ToolResult


class BashTool(BaseTool):
    name = "bash"
    description = (
        "Execute a bash command and return its output. "
        "Commands run in the current working directory."
    )

    @property
    def risk_level(self) -> str:
        return "dangerous"

    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The bash command to execute.",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds (default 120, max 600).",
                    "default": 120,
                },
            },
            "required": ["command"],
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        command = kwargs.get("command", "")
        timeout = min(kwargs.get("timeout", 120), 600)

        if not command.strip():
            return ToolResult(error="Empty command", is_error=True)

        try:
            result = subprocess.run(
                ["bash", "-c", command],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                error=f"Command timed out after {timeout} seconds",
                is_error=True,
            )
        except FileNotFoundError:
            try:
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    shell=True,
                )
            except subprocess.TimeoutExpired:
                return ToolResult(
                    error=f"Command timed out after {timeout} seconds",
                    is_error=True,
                )

        output_parts = []
        if result.stdout:
            output_parts.append(result.stdout)
        if result.stderr:
            output_parts.append(f"STDERR:\n{result.stderr}")

        output = "\n".join(output_parts).strip()

        if len(output) > 50000:
            output = output[:25000] + "\n\n... (output truncated) ...\n\n" + output[-25000:]

        if result.returncode != 0:
            return ToolResult(
                output=output,
                error=f"Exit code: {result.returncode}",
                is_error=True,
                metadata={"exit_code": result.returncode},
            )

        return ToolResult(output=output or "(no output)")
