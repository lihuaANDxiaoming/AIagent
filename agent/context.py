"""Conversation context management."""

from __future__ import annotations

from pathlib import Path
from typing import Any


class ContextManager:
    def __init__(self, system_prompt: str, workspace: Path, recent_limit: int = 20,
                 memory_context: str = ""):
        self.system_prompt = system_prompt
        self.workspace = workspace
        self.recent_limit = max(4, recent_limit)
        self.history: list[dict[str, Any]] = []
        self.memory_context = memory_context
        self.summary = ""

    def add(self, message: dict[str, Any]) -> None:
        self.history.append(message)

    def workspace_state(self) -> str:
        entries = sorted(p.relative_to(self.workspace).as_posix() for p in self.workspace.rglob("*") if p.is_file())
        return "Workspace files:\n" + ("\n".join(entries[:200]) or "(empty)")

    def messages(self) -> list[dict[str, Any]]:
        parts = [self.system_prompt, self.workspace_state()]
        if self.memory_context:
            parts.append(self.memory_context)
        system = {"role": "system", "content": "\n\n".join(parts)}
        if len(self.history) <= self.recent_limit:
            return [system, *self.history]
        omitted_messages = self.history[:-self.recent_limit]
        self.summary = self._summarize(omitted_messages)
        summary = {"role": "system", "content": "Earlier history summary:\n" + self.summary}
        return [system, summary, *self.history[-self.recent_limit:]]

    @staticmethod
    def _summarize(messages: list[dict[str, Any]]) -> str:
        useful: list[str] = []
        for message in messages[-12:]:
            role = message.get("role", "unknown")
            content = str(message.get("content") or "").strip()
            if not content or content.lower().startswith(("created ", "updated ")):
                continue
            content = " ".join(content.split())[:300]
            useful.append(f"- {role}: {content}")
        return "\n".join(useful) or f"{len(messages)} low-information messages were truncated."

    def reset(self) -> None:
        self.history.clear()
        self.summary = ""
