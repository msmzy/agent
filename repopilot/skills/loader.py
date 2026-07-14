"""Skill discovery: scan directories, parse YAML frontmatter, extract metadata.

Progressive context loading: only frontmatter is read at startup.
Full skill body is loaded on-demand when the skill is invoked.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class SkillMeta:
    name: str
    description: str
    triggers: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    applicable_when: str = ""
    not_applicable_when: str = ""
    examples: list[str] = field(default_factory=list)
    path: Path = field(default_factory=lambda: Path("."))

    @property
    def frontmatter_text(self) -> str:
        parts = [f"**{self.name}**: {self.description}"]
        if self.triggers:
            parts.append(f"Triggers: {', '.join(self.triggers)}")
        if self.tags:
            parts.append(f"Tags: {', '.join(self.tags)}")
        if self.applicable_when:
            parts.append(f"Use when: {self.applicable_when}")
        if self.not_applicable_when:
            parts.append(f"Skip when: {self.not_applicable_when}")
        return "\n".join(parts)


FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


class SkillLoader:
    """Discovers skills from directories and provides lazy body loading."""

    def __init__(self, skill_dirs: list[str | Path]) -> None:
        self.skill_dirs = [Path(d) for d in skill_dirs]
        self._skills: dict[str, SkillMeta] = {}
        self._scan()

    def _scan(self) -> None:
        for skill_dir in self.skill_dirs:
            if not skill_dir.exists():
                continue
            for skill_path in skill_dir.iterdir():
                if skill_path.is_dir():
                    skill_file = skill_path / "SKILL.md"
                    if skill_file.exists():
                        meta = self._parse_frontmatter(skill_file)
                        if meta:
                            self._skills[meta.name] = meta
                elif skill_path.suffix == ".md":
                    meta = self._parse_frontmatter(skill_path)
                    if meta:
                        self._skills[meta.name] = meta

    def _parse_frontmatter(self, path: Path) -> SkillMeta | None:
        try:
            content = path.read_text(encoding="utf-8")
        except (PermissionError, OSError):
            return None

        match = FRONTMATTER_RE.match(content)
        if not match:
            return None

        try:
            fm: dict[str, Any] = yaml.safe_load(match.group(1)) or {}
        except yaml.YAMLError:
            return None

        name = fm.get("name", path.stem)
        description = fm.get("description", "")
        if not description:
            return None

        return SkillMeta(
            name=name,
            description=description,
            triggers=_ensure_list(fm.get("triggers", [])),
            tags=_ensure_list(fm.get("tags", [])),
            applicable_when=fm.get("applicable_when", ""),
            not_applicable_when=fm.get("not_applicable_when", ""),
            examples=_ensure_list(fm.get("examples", [])),
            path=path,
        )

    def list_skills(self) -> list[SkillMeta]:
        return list(self._skills.values())

    def get_skill(self, name: str) -> SkillMeta | None:
        return self._skills.get(name)

    def load_body(self, name: str) -> str | None:
        """Load full skill body (everything after frontmatter). Called on invocation."""
        meta = self._skills.get(name)
        if not meta:
            return None
        try:
            content = meta.path.read_text(encoding="utf-8")
        except (PermissionError, OSError):
            return None
        match = FRONTMATTER_RE.match(content)
        if match:
            return content[match.end():]
        return content

    def get_all_frontmatter(self) -> str:
        """Return all skill frontmatters as a single string for LLM routing."""
        return "\n\n".join(s.frontmatter_text for s in self._skills.values())

    def reload(self) -> None:
        self._skills.clear()
        self._scan()


def _ensure_list(val: Any) -> list[str]:
    if isinstance(val, list):
        return [str(v) for v in val]
    if isinstance(val, str):
        return [val]
    return []
