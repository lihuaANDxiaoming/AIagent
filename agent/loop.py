"""LLM/tool execution loop."""

from __future__ import annotations

import json
from typing import Any, Callable

from agent.context import ContextManager
from tools.registry import ToolRegistry
from agent.checkpoint import CheckpointManager
from agent.memory import MemoryManager
from agent.safety import Decision, SafetyPolicy


class AgentLoop:
    def __init__(self, llm: Any, registry: ToolRegistry, context: ContextManager,
                 max_rounds: int = 20, on_event: Callable[[str, Any], None] | None = None,
                 safety: SafetyPolicy | None = None, checkpoint: CheckpointManager | None = None,
                 memory: MemoryManager | None = None,
                 confirm: Callable[[str], bool] | None = None):
        self.llm = llm
        self.registry = registry
        self.context = context
        self.max_rounds = max_rounds
        self.on_event = on_event or (lambda _event, _data: None)
        self.safety = safety
        self.checkpoint = checkpoint
        self.memory = memory
        self.confirm = confirm or (lambda _prompt: False)

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
                if self.memory:
                    self.memory.remember("completed_tasks", {"task": task, "result": final[:500]})
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
                if not isinstance(shown_args, dict):
                    result = "Tool error (JSONDecodeError): arguments must be a JSON object."
                else:
                    result = self._execute_tool(name, shown_args)
                self.on_event("tool_result", result)
                self.context.add({"role": "tool", "tool_call_id": call.id, "content": result})

        final = f"Stopped after reaching the maximum of {self.max_rounds} rounds."
        self.on_event("final", final)
        return final

    def _execute_tool(self, name: str, arguments: dict[str, Any]) -> str:
        if self.safety:
            verdict = self.safety.evaluate(name, arguments)
            self.on_event("safety", {"decision": verdict.decision.value, "reason": verdict.reason})
            if verdict.decision is Decision.DENY:
                return f"Permission denied: {verdict.reason}"
            if verdict.decision is Decision.CONFIRM and not self.confirm(
                    f"Allow {name} with {arguments}? Reason: {verdict.reason}"):
                return f"Permission denied by user: {verdict.reason}"
        if self.checkpoint and name in {"write_file", "edit_file", "delete_file"}:
            checkpoint_id = self.checkpoint.create_checkpoint(f"Before {name}: {arguments.get('path', '')}")
            self.on_event("checkpoint", checkpoint_id)
        result = self.registry.execute(name, arguments)
        if self.memory:
            self.memory.record_tool_success(name, arguments, result)
        return result
