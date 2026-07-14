"""File write tool with safety checks."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from repopilot.tools.base import BaseTool, ToolResult


class WriteFileTool(BaseTool):
    name = "write_file"
    description = (
        "Write content to a file. Creates parent directories if needed. "
        "Overwrites existing files."
    )

    @property
    def risk_level(self) -> str:
        return "write"

    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Absolute or relative path to the file to write.",
                },
                "content": {
                    "type": "string",
                    "description": "The content to write to the file.",
                },
            },
            "required": ["file_path", "content"],
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        file_path = kwargs.get("file_path", "")
        content = kwargs.get("content", "")

        path = Path(file_path).resolve()

        sensitive_patterns = [".env", "credentials", "secret", ".pem", ".key"]
        if any(p in path.name.lower() for p in sensitive_patterns):
            return ToolResult(
                error=f"Refusing to write potentially sensitive file: {path.name}",
                is_error=True,
            )

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        except PermissionError:
            return ToolResult(error=f"Permission denied: {path}", is_error=True)
        except OSError as e:
            return ToolResult(error=f"Write failed: {e}", is_error=True)

        return ToolResult(output=f"Successfully wrote {len(content)} bytes to {path}")
