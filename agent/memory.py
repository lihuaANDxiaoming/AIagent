"""Persistent project memory."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any


DEFAULT_MEMORY: dict[str, Any] = {
    "project_info": {}, "important_files": [], "commands": {},
    "decisions": [], "constraints": [], "completed_tasks": [],
}


class MemoryManager:
    def __init__(self, path: Path):
        self.path = path
        self.data: dict[str, Any] = deepcopy(DEFAULT_MEMORY)
        self.load()

    def load(self) -> dict[str, Any]:
        if self.path.exists():
            try:
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    self.data.update(loaded)
            except (json.JSONDecodeError, OSError):
                pass
        return self.data

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)

    def remember(self, key: str, value: Any) -> None:
        if key not in DEFAULT_MEMORY:
            raise KeyError(f"Unsupported memory category: {key}")
        current = self.data[key]
        if isinstance(current, list):
            if value not in current:
                current.append(value)
        elif isinstance(current, dict) and isinstance(value, dict):
            current.update(value)
        else:
            self.data[key] = value
        self.save()

    def recall(self, key: str | None = None) -> Any:
        return self.data.get(key) if key else deepcopy(self.data)

    def as_context(self) -> str:
        meaningful = {key: value for key, value in self.data.items() if value}
        return "Long-term project memory:\n" + (json.dumps(meaningful, ensure_ascii=False, indent=2) if meaningful else "(empty)")

    def record_tool_success(self, name: str, arguments: dict[str, Any], result: str) -> None:
        if result.startswith("Tool error") or result.startswith("Permission"):
            return
        if name in {"write_file", "edit_file", "delete_file", "read_file"} and arguments.get("path"):
            self.remember("important_files", str(arguments["path"]))
        if name == "run_command" and arguments.get("command") and "Exit code: 0" in result:
            self.remember("commands", {"last_successful": str(arguments["command"])})
