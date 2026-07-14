"""Tool registry with deterministic ordering for prompt cache stability."""

from __future__ import annotations

from typing import Any

from repopilot.tools.base import BaseTool, ToolResult


class ToolRegistry:
    def __init__(self) -> None:
        self._builtin: dict[str, BaseTool] = {}
        self._dynamic: dict[str, BaseTool] = {}
        self._builtin_order: list[str] = []

    def register(self, tool: BaseTool, *, builtin: bool = True) -> None:
        if builtin:
            self._builtin[tool.name] = tool
            if tool.name not in self._builtin_order:
                self._builtin_order.append(tool.name)
        else:
            self._dynamic[tool.name] = tool

    def unregister(self, name: str) -> None:
        self._builtin.pop(name, None)
        self._dynamic.pop(name, None)
        if name in self._builtin_order:
            self._builtin_order.remove(name)

    def get(self, name: str) -> BaseTool | None:
        return self._builtin.get(name) or self._dynamic.get(name)

    def execute(self, name: str, **kwargs: Any) -> ToolResult:
        tool = self.get(name)
        if tool is None:
            return ToolResult(error=f"Unknown tool: {name}", is_error=True)
        return tool.execute(**kwargs)

    def list_tools(self) -> list[BaseTool]:
        """Return tools in deterministic order: builtins first (fixed order), then dynamic (sorted by name).

        Stable ordering preserves prompt cache prefix across requests.
        """
        ordered = [self._builtin[n] for n in self._builtin_order if n in self._builtin]
        dynamic_sorted = sorted(self._dynamic.values(), key=lambda t: t.name)
        return ordered + dynamic_sorted

    def to_api_format(self) -> list[dict[str, Any]]:
        return [tool.to_api_format() for tool in self.list_tools()]
