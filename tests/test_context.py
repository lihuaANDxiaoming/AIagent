from pathlib import Path

from agent.context import ContextManager


def test_context_keeps_recent_messages_and_workspace_state(tmp_path: Path):
    (tmp_path / "main.py").write_text("", encoding="utf-8")
    context = ContextManager("prompt", tmp_path, recent_limit=4)
    for number in range(6):
        context.add({"role": "user", "content": str(number)})
    messages = context.messages()
    assert "main.py" in messages[0]["content"]
    assert "Earlier history summary" in messages[1]["content"]
    assert "0" in messages[1]["content"]
    assert [m["content"] for m in messages[-4:]] == ["2", "3", "4", "5"]


def _tool_call(call_id: str):
    return {"id": call_id, "type": "function", "function": {
        "name": "read_file", "arguments": '{"path":"app.py"}'}}


def test_context_keeps_tool_call_and_all_results_as_one_group(tmp_path: Path):
    context = ContextManager("prompt", tmp_path, recent_limit=4)
    context.add({"role": "user", "content": "old task"})
    context.add({"role": "assistant", "content": None,
                 "tool_calls": [_tool_call("call-1"), _tool_call("call-2")]})
    context.add({"role": "tool", "tool_call_id": "call-1", "content": "first result"})
    context.add({"role": "tool", "tool_call_id": "call-2", "content": "second result"})
    context.add({"role": "assistant", "content": "done"})

    recent = context.messages()[2:]
    assert [message["role"] for message in recent] == ["assistant", "tool", "tool", "assistant"]
    call_ids = {call["id"] for call in recent[0]["tool_calls"]}
    assert {message["tool_call_id"] for message in recent[1:3]} == call_ids


def test_atomic_tool_group_may_exceed_soft_limit(tmp_path: Path):
    context = ContextManager("prompt", tmp_path, recent_limit=4)
    context.add({"role": "user", "content": "old"})
    calls = [_tool_call(f"call-{number}") for number in range(4)]
    context.add({"role": "assistant", "content": None, "tool_calls": calls})
    for number in range(4):
        context.add({"role": "tool", "tool_call_id": f"call-{number}", "content": str(number)})

    recent = context.messages()[2:]
    assert len(recent) == 5
    assert recent[0]["role"] == "assistant"
    assert all(message["role"] == "tool" for message in recent[1:])


def test_orphaned_tool_message_is_not_sent(tmp_path: Path):
    context = ContextManager("prompt", tmp_path, recent_limit=4)
    context.history = [
        {"role": "user", "content": "one"},
        {"role": "tool", "tool_call_id": "missing", "content": "orphan"},
        {"role": "user", "content": "two"},
        {"role": "user", "content": "three"},
        {"role": "user", "content": "four"},
    ]

    messages = context.messages()
    assert not any(message.get("role") == "tool" for message in messages)
