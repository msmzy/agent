"""Grep content search tool using subprocess."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from repopilot.tools.base import BaseTool, ToolResult


class GrepTool(BaseTool):
    name = "grep"
    description = (
        "Search file contents using regex patterns. "
        "Supports file type filtering and context lines."
    )

    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Regex pattern to search for.",
                },
                "path": {
                    "type": "string",
                    "description": "File or directory to search in.",
                },
                "glob": {
                    "type": "string",
                    "description": 'Glob filter for files (e.g. "*.py").',
                },
                "context": {
                    "type": "integer",
                    "description": "Lines of context around each match.",
                },
                "case_insensitive": {
                    "type": "boolean",
                    "description": "Case insensitive search.",
                    "default": False,
                },
            },
            "required": ["pattern"],
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        pattern = kwargs.get("pattern", "")
        search_path = kwargs.get("path", ".")
        file_glob = kwargs.get("glob")
        context = kwargs.get("context", 0)
        case_insensitive = kwargs.get("case_insensitive", False)

        path = Path(search_path).resolve()
        if not path.exists():
            return ToolResult(error=f"Path not found: {path}", is_error=True)

        cmd = self._build_command(pattern, str(path), file_glob, context, case_insensitive)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(path) if path.is_dir() else str(path.parent),
            )
        except FileNotFoundError:
            return self._fallback_grep(pattern, path, file_glob, case_insensitive)
        except subprocess.TimeoutExpired:
            return ToolResult(error="Search timed out after 30 seconds", is_error=True)

        output = result.stdout.strip()
        if not output:
            return ToolResult(output="No matches found.")

        lines = output.split("\n")
        if len(lines) > 250:
            output = "\n".join(lines[:250]) + f"\n\n... ({len(lines) - 250} more lines)"

        return ToolResult(output=output)

    def _build_command(
        self,
        pattern: str,
        path: str,
        file_glob: str | None,
        context: int,
        case_insensitive: bool,
    ) -> list[str]:
        cmd = ["rg", "--no-heading", "-n", pattern]
        if file_glob:
            cmd.extend(["--glob", file_glob])
        if context > 0:
            cmd.extend(["-C", str(context)])
        if case_insensitive:
            cmd.append("-i")
        cmd.append(path)
        return cmd

    def _fallback_grep(
        self, pattern: str, path: Path, file_glob: str | None, case_insensitive: bool
    ) -> ToolResult:
        """Fallback to Python-based grep when rg is not available."""
        import re

        flags = re.IGNORECASE if case_insensitive else 0
        try:
            regex = re.compile(pattern, flags)
        except re.error as e:
            return ToolResult(error=f"Invalid regex: {e}", is_error=True)

        results = []
        files = path.rglob(file_glob or "*") if path.is_dir() else [path]
        for f in files:
            if not f.is_file():
                continue
            try:
                lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
                for i, line in enumerate(lines, 1):
                    if regex.search(line):
                        results.append(f"{f}:{i}:{line}")
            except (PermissionError, OSError):
                continue
            if len(results) >= 250:
                break

        if not results:
            return ToolResult(output="No matches found.")
        return ToolResult(output="\n".join(results))
