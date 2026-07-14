"""Glob file search tool."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from repopilot.tools.base import BaseTool, ToolResult


class GlobTool(BaseTool):
    name = "glob"
    description = (
        "Search for files matching a glob pattern. "
        "Returns matching file paths sorted by modification time."
    )

    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": 'Glob pattern to match (e.g. "**/*.py", "src/**/*.ts").',
                },
                "path": {
                    "type": "string",
                    "description": "Directory to search in. Defaults to current directory.",
                },
            },
            "required": ["pattern"],
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        pattern = kwargs.get("pattern", "")
        search_path = kwargs.get("path", ".")

        base = Path(search_path).resolve()
        if not base.exists():
            return ToolResult(error=f"Directory not found: {base}", is_error=True)

        try:
            matches = sorted(base.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
        except OSError as e:
            return ToolResult(error=f"Glob failed: {e}", is_error=True)

        if not matches:
            return ToolResult(output="No files matched the pattern.")

        limit = 200
        lines = [str(m) for m in matches[:limit]]
        output = "\n".join(lines)
        if len(matches) > limit:
            output += f"\n\n... ({len(matches) - limit} more files)"

        return ToolResult(
            output=output,
            metadata={"total_matches": len(matches)},
        )
