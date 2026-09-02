"""LLM/tool execution loop."""

from __future__ import annotations

import json
from typing import Any, Callable

from agent.context import ContextManager
from tools.registry import ToolRegistry


class AgentLoop:
    def __init__(self, llm: Any, registry: ToolRegistry, context: ContextManager,
                 max_rounds: int = 20, on_event: Callable[[str, Any], None] | None = None):
        self.llm = llm
        self.registry = registry
        self.context = context
        self.max_rounds = max_rounds
        self.on_event = on_event or (lambda _event, _data: None)

    def run(self, task: str) -> str:
        self.context.add({"role": "user", "content": task})
        for round_number in range(1, self.max_rounds + 1):
            self.on_event("status", f"Round {round_number}: asking model")
            response = self.llm.chat(self.context.messages(), self.registry.schemas)
            message = response.choices[0].message
            tool_calls = message.tool_calls or []

            assistant: dict[str, Any] = {"role": "assistant", "content": message.content}
            if tool_calls:
                assistant["tool_calls"] = [call.model_dump(exclude_none=True) for call in tool_calls]
            self.context.add(assistant)

            if not tool_calls:
                final = message.content or "Task completed without a textual response."
                self.on_event("final", final)
                return final

            for call in tool_calls:
                name = call.function.name
                raw_args = call.function.arguments
                try:
                    shown_args = json.loads(raw_args)
                except json.JSONDecodeError:
                    shown_args = raw_args
                self.on_event("tool_call", {"name": name, "arguments": shown_args})
                result = self.registry.execute(name, raw_args)
                self.on_event("tool_result", result)
                self.context.add({"role": "tool", "tool_call_id": call.id, "content": result})

        final = f"Stopped after reaching the maximum of {self.max_rounds} rounds."
        self.on_event("final", final)
        return final
