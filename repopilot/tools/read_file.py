"""File read tool with line number display and range support."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from repopilot.tools.base import BaseTool, ToolResult


class ReadFileTool(BaseTool):
    name = "read_file"
    description = (
        "Read a file from the filesystem. Returns content with line numbers. "
        "Supports optional offset and limit for large files."
    )

    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Absolute or relative path to the file to read.",
                },
                "offset": {
                    "type": "integer",
                    "description": "Line number to start reading from (1-based).",
                    "minimum": 1,
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of lines to read.",
                    "minimum": 1,
                },
            },
            "required": ["file_path"],
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        file_path = kwargs.get("file_path", "")
        offset = kwargs.get("offset", 1)
        limit = kwargs.get("limit", 2000)

        path = Path(file_path).resolve()
        if not path.exists():
            return ToolResult(error=f"File not found: {path}", is_error=True)
        if not path.is_file():
            return ToolResult(error=f"Not a file: {path}", is_error=True)

        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except PermissionError:
            return ToolResult(error=f"Permission denied: {path}", is_error=True)

        lines = content.splitlines()
        total = len(lines)
        start = max(0, offset - 1)
        end = min(total, start + limit)
        selected = lines[start:end]

        numbered = []
        for i, line in enumerate(selected, start=start + 1):
            numbered.append(f"{i}\t{line}")

        output = "\n".join(numbered)
        if end < total:
            output += f"\n\n... ({total - end} more lines)"

        return ToolResult(
            output=output,
            metadata={"file_path": str(path), "total_lines": total},
        )
