"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    model: str = "gpt-4o-mini"
    api_key: str | None = None
    base_url: str | None = None
    workspace: Path = Path(__file__).parent / "workspace"
    max_rounds: int = 20
    context_window: int = 20
    command_timeout: int = 120

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            model=os.getenv("AGENT_MODEL", "gpt-4o-mini"),
            api_key=os.getenv("AGENT_API_KEY") or os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("AGENT_BASE_URL"),
            workspace=Path(os.getenv("AGENT_WORKSPACE", str(Path(__file__).parent / "workspace"))).resolve(),
            max_rounds=int(os.getenv("AGENT_MAX_ROUNDS", "20")),
            context_window=int(os.getenv("AGENT_CONTEXT_WINDOW", "20")),
            command_timeout=int(os.getenv("AGENT_COMMAND_TIMEOUT", "120")),
        )
