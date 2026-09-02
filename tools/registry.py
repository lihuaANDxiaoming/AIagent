"""Tool schemas and dispatch layer."""

from __future__ import annotations

import json
from typing import Any, Callable

from tools.filesystem import FileSystemTools
from tools.shell import ShellTools


def _schema(name: str, description: str, properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {"type": "function", "function": {"name": name, "description": description,
            "parameters": {"type": "object", "properties": properties, "required": required,
                           "additionalProperties": False}}}


class ToolRegistry:
    def __init__(self, filesystem: FileSystemTools, shell: ShellTools):
        string = lambda description: {"type": "string", "description": description}
        self._handlers: dict[str, Callable[..., str]] = {
            "list_files": filesystem.list_files,
            "read_file": filesystem.read_file,
            "write_file": filesystem.write_file,
            "edit_file": filesystem.edit_file,
            "search_text": filesystem.search_text,
            "run_command": shell.run_command,
        }
        self.schemas = [
            _schema("list_files", "List files and directories.", {"path": string("Relative directory; defaults to .")}, []),
            _schema("read_file", "Read a UTF-8 text file.", {"path": string("Relative file path")}, ["path"]),
            _schema("write_file", "Create a new UTF-8 text file.", {"path": string("Relative file path"), "content": string("Complete content")}, ["path", "content"]),
            _schema("edit_file", "Replace one unique text fragment in an existing file.", {"path": string("Relative file path"), "old_text": string("Exact existing text"), "new_text": string("Replacement text")}, ["path", "old_text", "new_text"]),
            _schema("search_text", "Search text recursively in workspace files.", {"query": string("Exact text to find"), "path": string("Relative path; defaults to .")}, ["query"]),
            _schema("run_command", "Run a command with the workspace as working directory.", {"command": string("Command to execute")}, ["command"]),
        ]

    def execute(self, name: str, arguments: str | dict[str, Any]) -> str:
        if name not in self._handlers:
            return f"Tool error: unknown tool {name!r}."
        try:
            args = json.loads(arguments) if isinstance(arguments, str) else arguments
            return self._handlers[name](**args)
        except Exception as exc:
            return f"Tool error ({type(exc).__name__}): {exc}"
