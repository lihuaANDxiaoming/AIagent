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

        # A message containing assistant tool_calls and all of its tool results
        # form one protocol-level unit. Slicing the raw list can leave a tool
        # result without its preceding call, which OpenAI-compatible APIs reject.
        recent_messages, omitted_messages = self._trim_complete_groups()
        self.summary = self._summarize(omitted_messages)
        summary = {"role": "system", "content": "Earlier history summary:\n" + self.summary}
        return [system, summary, *recent_messages]

    def _trim_complete_groups(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        groups: list[list[dict[str, Any]]] = []
        index = 0
        while index < len(self.history):
            message = self.history[index]
            if message.get("role") == "assistant" and message.get("tool_calls"):
                group = [message]
                expected_ids = {
                    call.get("id") for call in message["tool_calls"]
                    if isinstance(call, dict) and call.get("id")
                }
                index += 1
                while index < len(self.history):
                    candidate = self.history[index]
                    if candidate.get("role") != "tool":
                        break
                    # Keep every contiguous tool result with its assistant call.
                    # The ID check documents the relationship but malformed tool
                    # results are kept here so they never become standalone.
                    if not expected_ids or candidate.get("tool_call_id") in expected_ids:
                        group.append(candidate)
                        index += 1
                        continue
                    break
                groups.append(group)
                continue

            # Never send an already-orphaned tool result to the API.
            if message.get("role") != "tool":
                groups.append([message])
            index += 1

        selected: list[list[dict[str, Any]]] = []
        selected_count = 0
        for group in reversed(groups):
            if selected and selected_count + len(group) > self.recent_limit:
                break
            selected.append(group)
            selected_count += len(group)
            # One atomic group may be larger than the configured limit; protocol
            # validity takes precedence over the soft context-count target.
            if selected_count >= self.recent_limit:
                break
        selected.reverse()

        recent = [message for group in selected for message in group]
        retained_ids = {id(message) for message in recent}
        omitted = [message for message in self.history if id(message) not in retained_ids]
        return recent, omitted

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
