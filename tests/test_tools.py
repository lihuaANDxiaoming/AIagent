from pathlib import Path

import pytest

from tools.filesystem import FileSystemTools
from tools.registry import ToolRegistry
from tools.shell import ShellTools


def test_filesystem_workflow(tmp_path: Path):
    fs = FileSystemTools(tmp_path)
    assert fs.list_files() == "(empty)"
    fs.write_file("src/app.py", "answer = 1\n")
    assert "src/" in fs.list_files()
    assert fs.read_file("src/app.py") == "answer = 1\n"
    fs.edit_file("src/app.py", "1", "42")
    assert fs.search_text("answer", ".") == "src/app.py:1: answer = 42"


def test_write_refuses_overwrite_and_edit_requires_unique_text(tmp_path: Path):
    fs = FileSystemTools(tmp_path)
    fs.write_file("a.txt", "x x")
    with pytest.raises(FileExistsError):
        fs.write_file("a.txt", "new")
    with pytest.raises(ValueError):
        fs.edit_file("a.txt", "x", "y")


def test_path_cannot_escape_workspace(tmp_path: Path):
    fs = FileSystemTools(tmp_path)
    with pytest.raises(ValueError):
        fs.read_file("../secret.txt")


def test_registry_returns_tool_errors(tmp_path: Path):
    registry = ToolRegistry(FileSystemTools(tmp_path), ShellTools(tmp_path))
    result = registry.execute("read_file", '{"path": "missing.txt"}')
    assert result.startswith("Tool error (FileNotFoundError)")
