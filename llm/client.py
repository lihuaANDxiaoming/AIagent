"""OpenAI-compatible LLM client.

DeepSeek, Qwen and Gemini expose OpenAI-compatible endpoints, so callers can
select them with AGENT_BASE_URL and AGENT_MODEL without changing agent code.
"""

from __future__ import annotations

from typing import Any


class LLMClient:
    def __init__(self, model: str, api_key: str | None = None, base_url: str | None = None):
        if not api_key:
            raise ValueError("Missing API key. Set AGENT_API_KEY or OPENAI_API_KEY.")
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("Install dependencies with: pip install -r requirements.txt") from exc

        kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self.client = OpenAI(**kwargs)
        self.model = model

    def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> Any:
        return self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
        )
