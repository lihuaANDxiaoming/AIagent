import json
from pathlib import Path
from types import SimpleNamespace

from agent.context import ContextManager
from agent.loop import AgentLoop
from agent.safety import SafetyPolicy


class FakeCall:
    def __init__(self, call_id: str, name: str, arguments: dict):
        self.id = call_id
        self.function = SimpleNamespace(name=name, arguments=json.dumps(arguments))

    def model_dump(self, exclude_none=True):
        return {"id": self.id, "type": "function", "function": {
            "name": self.function.name, "arguments": self.function.arguments}}


def response(content=None, calls=None):
    message = SimpleNamespace(content=content, tool_calls=calls or [])
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class FakeLLM:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.seen_messages = []

    def chat(self, messages, tools):
        self.seen_messages.append(messages)
        return next(self.responses)


class FakeRegistry:
    schemas = []

    def __init__(self, results):
        self.results = iter(results)
        self.calls = []

    def execute(self, name, arguments):
        self.calls.append((name, arguments))
        return next(self.results)


def test_tool_failure_is_injected_and_model_can_recover(tmp_path: Path):
    llm = FakeLLM([
        response(calls=[FakeCall("1", "run_command", {"command": "pytest"})]),
        response(content="Recovered after reading the test failure."),
    ])
    registry = FakeRegistry(["Exit code: 1\nstderr:\nAssertionError"])
    context = ContextManager("prompt", tmp_path)
    loop = AgentLoop(llm, registry, context, safety=SafetyPolicy(tmp_path))

    assert loop.run("fix tests").startswith("Recovered")
    second_round = llm.seen_messages[1]
    assert any(message.get("role") == "tool" and "AssertionError" in message["content"]
               for message in second_round)


def test_denied_operation_is_fed_back_without_execution(tmp_path: Path):
    llm = FakeLLM([
        response(calls=[FakeCall("1", "run_command", {"command": "shutdown"})]),
        response(content="I will not run the unsafe command."),
    ])
    registry = FakeRegistry([])
    context = ContextManager("prompt", tmp_path)
    loop = AgentLoop(llm, registry, context, safety=SafetyPolicy(tmp_path))

    loop.run("unsafe task")
    assert registry.calls == []
    assert any("Permission denied" in (message.get("content") or "")
               for message in llm.seen_messages[1])
