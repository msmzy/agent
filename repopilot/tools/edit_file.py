"""File edit tool using exact string replacement."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from repopilot.tools.base import BaseTool, ToolResult


class EditFileTool(BaseTool):
    name = "edit_file"
    description = (
        "Edit a file by replacing an exact string match. "
        "The old_string must be unique in the file unless replace_all is true."
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
                    "description": "Path to the file to edit.",
                },
                "old_string": {
                    "type": "string",
                    "description": "The exact text to find and replace.",
                },
                "new_string": {
                    "type": "string",
                    "description": "The replacement text.",
                },
                "replace_all": {
                    "type": "boolean",
                    "description": "Replace all occurrences if true.",
                    "default": False,
                },
            },
            "required": ["file_path", "old_string", "new_string"],
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        file_path = kwargs.get("file_path", "")
        old_string = kwargs.get("old_string", "")
        new_string = kwargs.get("new_string", "")
        replace_all = kwargs.get("replace_all", False)

        path = Path(file_path).resolve()
        if not path.exists():
            return ToolResult(error=f"File not found: {path}", is_error=True)

        try:
            content = path.read_text(encoding="utf-8")
        except PermissionError:
            return ToolResult(error=f"Permission denied: {path}", is_error=True)

        if old_string == new_string:
            return ToolResult(error="old_string and new_string are identical", is_error=True)

        count = content.count(old_string)
        if count == 0:
            return ToolResult(error="old_string not found in file", is_error=True)
        if count > 1 and not replace_all:
            return ToolResult(
                error=f"old_string found {count} times. Use replace_all=true or provide more context for uniqueness.",
                is_error=True,
            )

        if replace_all:
            new_content = content.replace(old_string, new_string)
        else:
            new_content = content.replace(old_string, new_string, 1)

        path.write_text(new_content, encoding="utf-8")
        replaced = count if replace_all else 1
        return ToolResult(output=f"Replaced {replaced} occurrence(s) in {path}")
