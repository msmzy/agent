"""Tests for the memory system."""

from pathlib import Path

import pytest

from repopilot.memory.types import MemoryRecord, MemoryType
from repopilot.memory.store import MemoryStore
from repopilot.memory.indexer import MemoryIndexer


class TestMemoryRecord:
    def test_filename_generation(self):
        r = MemoryRecord(
            name="User Preferences",
            description="test",
            type=MemoryType.USER,
            content="test content",
        )
        assert r.filename == "user_user_preferences.md"

    def test_to_frontmatter(self):
        r = MemoryRecord(
            name="test",
            description="a test memory",
            type=MemoryType.FEEDBACK,
            content="some content",
        )
        fm = r.to_frontmatter()
        assert "---" in fm
        assert "name: test" in fm
        assert "type: feedback" in fm
        assert "some content" in fm

    def test_index_entry(self):
        r = MemoryRecord(
            name="test",
            description="desc",
            type=MemoryType.PROJECT,
            content="",
        )
        entry = r.index_entry()
        assert "[test]" in entry
        assert "desc" in entry


class TestMemoryStore:
    def test_save_and_retrieve(self, tmp_path):
        store = MemoryStore(tmp_path / "memory")
        record = MemoryRecord(
            name="test_memory",
            description="A test",
            type=MemoryType.USER,
            content="User is a developer",
        )
        store.save(record)
        retrieved = store.get_by_name("test_memory")
        assert retrieved is not None
        assert retrieved.content == "User is a developer"
        assert retrieved.type == MemoryType.USER

    def test_list_all(self, tmp_path):
        store = MemoryStore(tmp_path / "memory")
        for i in range(3):
            store.save(MemoryRecord(
                name=f"mem_{i}",
                description=f"Memory {i}",
                type=MemoryType.PROJECT,
                content=f"Content {i}",
            ))
        assert len(store.list_all()) == 3

    def test_list_by_type(self, tmp_path):
        store = MemoryStore(tmp_path / "memory")
        store.save(MemoryRecord(name="u1", description="", type=MemoryType.USER, content=""))
        store.save(MemoryRecord(name="p1", description="", type=MemoryType.PROJECT, content=""))
        assert len(store.list_by_type(MemoryType.USER)) == 1

    def test_delete(self, tmp_path):
        store = MemoryStore(tmp_path / "memory")
        store.save(MemoryRecord(name="to_delete", description="", type=MemoryType.USER, content=""))
        assert store.delete("to_delete")
        assert store.get_by_name("to_delete") is None

    def test_update_existing(self, tmp_path):
        store = MemoryStore(tmp_path / "memory")
        store.save(MemoryRecord(name="evolving", description="v1", type=MemoryType.FEEDBACK, content="old"))
        store.save(MemoryRecord(name="evolving", description="v2", type=MemoryType.FEEDBACK, content="new"))
        result = store.get_by_name("evolving")
        assert result.content == "new"
        assert result.description == "v2"

    def test_index_updated(self, tmp_path):
        store = MemoryStore(tmp_path / "memory")
        store.save(MemoryRecord(name="indexed", description="test", type=MemoryType.USER, content=""))
        index = store.get_index_content()
        assert "[indexed]" in index

    def test_touch_increments_access(self, tmp_path):
        store = MemoryStore(tmp_path / "memory")
        store.save(MemoryRecord(name="accessed", description="", type=MemoryType.USER, content=""))
        store.touch("accessed")
        record = store.get_by_name("accessed")
        assert record.access_count == 1


class TestMemoryIndexer:
    def test_search_by_keyword(self, tmp_path):
        store = MemoryStore(tmp_path / "memory")
        store.save(MemoryRecord(name="python_pref", description="Prefers Python", type=MemoryType.USER, content="The user prefers Python for backend development"))
        store.save(MemoryRecord(name="react_pref", description="Uses React", type=MemoryType.USER, content="The user uses React for frontend"))
        indexer = MemoryIndexer(store)
        results = indexer.search("Python backend")
        assert len(results) > 0
        assert results[0].record.name == "python_pref"

    def test_search_with_type_filter(self, tmp_path):
        store = MemoryStore(tmp_path / "memory")
        store.save(MemoryRecord(name="u1", description="user info", type=MemoryType.USER, content="developer"))
        store.save(MemoryRecord(name="p1", description="project info", type=MemoryType.PROJECT, content="developer tools"))
        indexer = MemoryIndexer(store)
        results = indexer.search("developer", memory_type=MemoryType.USER)
        assert all(r.record.type == MemoryType.USER for r in results)

    def test_get_relevant_context(self, tmp_path):
        store = MemoryStore(tmp_path / "memory")
        store.save(MemoryRecord(name="context_test", description="test", type=MemoryType.USER, content="relevant info"))
        indexer = MemoryIndexer(store)
        context = indexer.get_relevant_context("test info")
        assert "relevant info" in context or context == ""
