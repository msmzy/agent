"""Tests for the tool system."""

import tempfile
from pathlib import Path

import pytest

from repopilot.tools.base import ToolResult
from repopilot.tools.read_file import ReadFileTool
from repopilot.tools.write_file import WriteFileTool
from repopilot.tools.edit_file import EditFileTool
from repopilot.tools.glob_tool import GlobTool
from repopilot.tools.grep_tool import GrepTool
from repopilot.tools.registry import ToolRegistry


class TestToolResult:
    def test_success_result(self):
        r = ToolResult(output="hello")
        assert not r.is_error
        assert r.to_api_format() == {"type": "text", "text": "hello"}

    def test_error_result(self):
        r = ToolResult(error="fail", is_error=True)
        assert r.is_error
        assert "Error: fail" in r.to_api_format()["text"]


class TestReadFileTool:
    def test_read_existing_file(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("line1\nline2\nline3\n")
        tool = ReadFileTool()
        result = tool.execute(file_path=str(f))
        assert not result.is_error
        assert "1\tline1" in result.output
        assert "2\tline2" in result.output

    def test_read_nonexistent_file(self):
        tool = ReadFileTool()
        result = tool.execute(file_path="/nonexistent/file.txt")
        assert result.is_error

    def test_read_with_offset_and_limit(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("\n".join(f"line{i}" for i in range(100)))
        tool = ReadFileTool()
        result = tool.execute(file_path=str(f), offset=10, limit=5)
        assert not result.is_error
        assert "10\tline9" in result.output


class TestWriteFileTool:
    def test_write_new_file(self, tmp_path):
        f = tmp_path / "new.txt"
        tool = WriteFileTool()
        result = tool.execute(file_path=str(f), content="hello world")
        assert not result.is_error
        assert f.read_text() == "hello world"

    def test_write_creates_parent_dirs(self, tmp_path):
        f = tmp_path / "a" / "b" / "c.txt"
        tool = WriteFileTool()
        result = tool.execute(file_path=str(f), content="deep")
        assert not result.is_error
        assert f.read_text() == "deep"

    def test_refuse_sensitive_files(self, tmp_path):
        f = tmp_path / ".env"
        tool = WriteFileTool()
        result = tool.execute(file_path=str(f), content="SECRET=x")
        assert result.is_error

    def test_risk_level(self):
        assert WriteFileTool().risk_level == "write"


class TestEditFileTool:
    def test_edit_unique_string(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("def hello():\n    return 'world'\n")
        tool = EditFileTool()
        result = tool.execute(
            file_path=str(f), old_string="'world'", new_string="'universe'"
        )
        assert not result.is_error
        assert "'universe'" in f.read_text()

    def test_edit_non_unique_fails(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("aaa\naaa\n")
        tool = EditFileTool()
        result = tool.execute(file_path=str(f), old_string="aaa", new_string="bbb")
        assert result.is_error

    def test_edit_replace_all(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("aaa\naaa\n")
        tool = EditFileTool()
        result = tool.execute(
            file_path=str(f), old_string="aaa", new_string="bbb", replace_all=True
        )
        assert not result.is_error
        assert f.read_text() == "bbb\nbbb\n"


class TestGlobTool:
    def test_glob_pattern(self, tmp_path):
        (tmp_path / "a.py").write_text("")
        (tmp_path / "b.py").write_text("")
        (tmp_path / "c.txt").write_text("")
        tool = GlobTool()
        result = tool.execute(pattern="*.py", path=str(tmp_path))
        assert not result.is_error
        assert "a.py" in result.output
        assert "b.py" in result.output
        assert "c.txt" not in result.output


class TestToolRegistry:
    def test_register_and_get(self):
        reg = ToolRegistry()
        tool = ReadFileTool()
        reg.register(tool)
        assert reg.get("read_file") is tool

    def test_deterministic_ordering(self):
        reg = ToolRegistry()
        reg.register(ReadFileTool())
        reg.register(WriteFileTool())
        reg.register(EditFileTool())
        tools = reg.list_tools()
        names = [t.name for t in tools]
        assert names == ["read_file", "write_file", "edit_file"]

    def test_execute_unknown_tool(self):
        reg = ToolRegistry()
        result = reg.execute("nonexistent")
        assert result.is_error

    def test_to_api_format(self):
        reg = ToolRegistry()
        reg.register(ReadFileTool())
        api = reg.to_api_format()
        assert len(api) == 1
        assert api[0]["name"] == "read_file"
        assert "input_schema" in api[0]
