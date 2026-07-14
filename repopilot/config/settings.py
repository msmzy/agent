"""Hierarchical configuration loading: global → project → local."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class PermissionRule(BaseModel):
    tool: str
    pattern: str = "*"
    action: str = "allow"


class Settings(BaseModel):
    model: str = Field(default="claude-sonnet-4-6")
    max_tokens: int = Field(default=8192)
    max_iterations: int = Field(default=50)
    temperature: float = Field(default=0.0)

    context_window: int = Field(default=200000)
    compress_threshold_warning: float = Field(default=0.70)
    compress_threshold_critical: float = Field(default=0.85)
    max_recent_tool_results: int = Field(default=5)

    permission_mode: str = Field(default="default")
    permissions: list[PermissionRule] = Field(default_factory=list)
    deny_rules: list[PermissionRule] = Field(default_factory=list)

    memory_dir: str = Field(default=".repopilot/memory")
    skills_dirs: list[str] = Field(default_factory=lambda: [".repopilot/skills", "skills"])

    global_config_dir: str = Field(default="~/.repopilot")
    project_config_dir: str = Field(default=".repopilot")

    def merge(self, other: dict[str, Any]) -> Settings:
        data = self.model_dump()
        for key, value in other.items():
            if key == "deny_rules":
                data["deny_rules"] = data.get("deny_rules", []) + value
            elif key == "permissions":
                data["permissions"] = data.get("permissions", []) + value
            else:
                data[key] = value
        return Settings(**data)


def _load_json(path: Path) -> dict[str, Any]:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def load_settings(working_dir: str | Path = ".") -> Settings:
    """Load settings with hierarchy: global → project → local.

    Later layers override earlier ones. deny_rules and permissions accumulate.
    """
    working_dir = Path(working_dir).resolve()
    global_dir = Path.home() / ".repopilot"
    project_dir = working_dir / ".repopilot"

    settings = Settings()

    for config_path in [
        global_dir / "settings.json",
        project_dir / "settings.json",
        project_dir / "settings.local.json",
    ]:
        layer = _load_json(config_path)
        if layer:
            settings = settings.merge(layer)

    return settings
