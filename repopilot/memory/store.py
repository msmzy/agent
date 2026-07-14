"""File-based memory storage using Markdown files with YAML frontmatter."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from repopilot.memory.types import MemoryRecord, MemoryType

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


class MemoryStore:
    """Manages memory records as Markdown files with a MEMORY.md index."""

    def __init__(self, memory_dir: str | Path) -> None:
        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self.memory_dir / "MEMORY.md"
        if not self._index_path.exists():
            self._index_path.write_text("# Memory Index\n", encoding="utf-8")

    def save(self, record: MemoryRecord) -> Path:
        """Save a memory record to disk and update the index."""
        existing = self.get_by_name(record.name)
        if existing:
            record.created_at = existing.created_at
            record.access_count = existing.access_count

        record.updated_at = datetime.now().isoformat()
        file_path = self.memory_dir / record.filename
        file_path.write_text(record.to_frontmatter(), encoding="utf-8")
        record.file_path = str(file_path)

        self._update_index(record)
        return file_path

    def get_by_name(self, name: str) -> MemoryRecord | None:
        for record in self.list_all():
            if record.name == name:
                return record
        return None

    def delete(self, name: str) -> bool:
        record = self.get_by_name(name)
        if not record:
            return False
        file_path = self.memory_dir / record.filename
        if file_path.exists():
            file_path.unlink()
        self._remove_from_index(record.name)
        return True

    def list_all(self) -> list[MemoryRecord]:
        records = []
        for f in self.memory_dir.glob("*.md"):
            if f.name == "MEMORY.md":
                continue
            record = self._parse_file(f)
            if record:
                records.append(record)
        return records

    def list_by_type(self, memory_type: MemoryType) -> list[MemoryRecord]:
        return [r for r in self.list_all() if r.type == memory_type]

    def touch(self, name: str) -> None:
        """Increment access count for a memory record."""
        record = self.get_by_name(name)
        if record:
            record.access_count += 1
            record.updated_at = datetime.now().isoformat()
            file_path = self.memory_dir / record.filename
            file_path.write_text(record.to_frontmatter(), encoding="utf-8")

    def get_index_content(self) -> str:
        if self._index_path.exists():
            return self._index_path.read_text(encoding="utf-8")
        return ""

    def _parse_file(self, path: Path) -> MemoryRecord | None:
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

        body = content[match.end():]
        try:
            memory_type = MemoryType(fm.get("type", "project"))
        except ValueError:
            memory_type = MemoryType.PROJECT

        return MemoryRecord(
            name=fm.get("name", path.stem),
            description=fm.get("description", ""),
            type=memory_type,
            content=body.strip(),
            file_path=str(path),
            created_at=str(fm.get("created_at", "")),
            updated_at=str(fm.get("updated_at", "")),
            access_count=int(fm.get("access_count", 0)),
        )

    def _update_index(self, record: MemoryRecord) -> None:
        content = self._index_path.read_text(encoding="utf-8")
        lines = content.split("\n")

        new_lines = [line for line in lines if record.filename not in line]

        insert_pos = len(new_lines)
        for i, line in enumerate(new_lines):
            if line.startswith("- [") and not line.startswith("# "):
                insert_pos = i
                break

        new_lines.insert(insert_pos, record.index_entry())
        self._index_path.write_text("\n".join(new_lines), encoding="utf-8")

    def _remove_from_index(self, name: str) -> None:
        content = self._index_path.read_text(encoding="utf-8")
        lines = content.split("\n")
        new_lines = [line for line in lines if f"[{name}]" not in line]
        self._index_path.write_text("\n".join(new_lines), encoding="utf-8")
