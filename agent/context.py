"""Conversation context management."""

from __future__ import annotations

from pathlib import Path
from typing import Any


class ContextManager:
    def __init__(self, system_prompt: str, workspace: Path, recent_limit: int = 20):
        self.system_prompt = system_prompt
        self.workspace = workspace
        self.recent_limit = max(4, recent_limit)
        self.history: list[dict[str, Any]] = []

    def add(self, message: dict[str, Any]) -> None:
        self.history.append(message)

    def workspace_state(self) -> str:
        entries = sorted(p.relative_to(self.workspace).as_posix() for p in self.workspace.rglob("*") if p.is_file())
        return "Workspace files:\n" + ("\n".join(entries[:200]) or "(empty)")

    def messages(self) -> list[dict[str, Any]]:
        system = {"role": "system", "content": self.system_prompt + "\n\n" + self.workspace_state()}
        if len(self.history) <= self.recent_limit:
            return [system, *self.history]
        omitted = len(self.history) - self.recent_limit
        summary = {"role": "system", "content": f"{omitted} earlier messages were omitted to fit the context window."}
        return [system, summary, *self.history[-self.recent_limit:]]

    def reset(self) -> None:
        self.history.clear()
