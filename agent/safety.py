"""Risk classification for agent tool calls."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any


class Decision(str, Enum):
    ALLOW = "ALLOW"
    CONFIRM = "CONFIRM"
    DENY = "DENY"


@dataclass(frozen=True)
class SafetyResult:
    decision: Decision
    reason: str


class SafetyPolicy:
    PATH_ARGUMENTS = {"list_files", "read_file", "write_file", "edit_file", "delete_file", "search_text"}
    WRITE_TOOLS = {"write_file", "edit_file", "delete_file"}

    def __init__(self, workspace: Path, blocked_commands: tuple[str, ...] = (),
                 confirm_commands: tuple[str, ...] = (), mode: str = "development"):
        self.workspace = workspace.resolve()
        self.blocked_commands = tuple(item.lower() for item in blocked_commands)
        self.confirm_commands = tuple(item.lower() for item in confirm_commands)
        self.mode = mode.lower()

    def evaluate(self, tool_name: str, arguments: dict[str, Any]) -> SafetyResult:
        if tool_name in self.PATH_ARGUMENTS:
            path = str(arguments.get("path", "."))
            target = (self.workspace / path).resolve()
            if target != self.workspace and self.workspace not in target.parents:
                return SafetyResult(Decision.DENY, f"Path is outside workspace: {path}")

        if self.mode == "readonly" and tool_name in self.WRITE_TOOLS | {"run_command"}:
            return SafetyResult(Decision.DENY, "Read-only mode blocks modifications and commands.")
        if self.mode == "strict" and tool_name in self.WRITE_TOOLS:
            return SafetyResult(Decision.CONFIRM, f"Strict mode requires approval for {tool_name}.")
        if tool_name == "delete_file":
            return SafetyResult(Decision.CONFIRM, "Deleting a file or directory requires approval.")
        if tool_name == "run_command":
            return self._evaluate_command(str(arguments.get("command", "")))
        return SafetyResult(Decision.ALLOW, "Operation is permitted inside the workspace.")

    def _evaluate_command(self, command: str) -> SafetyResult:
        normalized = " ".join(command.lower().split())
        hard_blocked = (
            r"rm\s+-[^\r\n]*r[^\r\n]*f[^\r\n]*\s+[/~](?:\s|$)",
            r"\b(?:shutdown|reboot|poweroff|halt)\b",
            r"(?:curl|wget)\b[^\r\n|]*\|\s*(?:ba)?sh\b",
            r"\b(?:format|diskpart)\b",
        )
        if any(re.search(pattern, normalized) for pattern in hard_blocked):
            return SafetyResult(Decision.DENY, "Dangerous system command is blocked.")
        if any(blocked in normalized for blocked in self.blocked_commands):
            return SafetyResult(Decision.DENY, "Command matches a configured blocked rule.")
        confirmation_patterns = (
            r"\b(?:pip|npm|pnpm|yarn)\s+install\b",
            r"\b(?:rm|rmdir|del|erase)\b",
            r"\bgit\s+(?:push|clean|reset)\b",
        )
        if any(re.search(pattern, normalized) for pattern in confirmation_patterns):
            return SafetyResult(Decision.CONFIRM, "Command may modify files, dependencies, or remote state.")
        if any(item in normalized for item in self.confirm_commands):
            return SafetyResult(Decision.CONFIRM, "Command matches a configured confirmation rule.")
        return SafetyResult(Decision.ALLOW, "Command is permitted.")
