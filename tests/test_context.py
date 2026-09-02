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
