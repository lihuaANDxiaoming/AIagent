"""Interactive command-line entry point."""

from __future__ import annotations

import json

from agent.context import ContextManager
from agent.checkpoint import CheckpointManager
from agent.loop import AgentLoop
from agent.memory import MemoryManager
from agent.prompt import SYSTEM_PROMPT
from agent.safety import SafetyPolicy
from config import Config
from llm.client import LLMClient
from tools.filesystem import FileSystemTools
from tools.registry import ToolRegistry
from tools.shell import ShellTools


def print_event(event: str, data: object) -> None:
    labels = {"status": "状态", "tool_call": "工具调用", "tool_result": "工具结果",
              "safety": "安全检查", "checkpoint": "检查点", "final": "最终回答"}
    if isinstance(data, dict):
        data = json.dumps(data, ensure_ascii=False, indent=2)
    print(f"\n[{labels.get(event, event)}]\n{data}")


def build_agent(config: Config) -> AgentLoop:
    config.workspace.mkdir(parents=True, exist_ok=True)
    filesystem = FileSystemTools(config.workspace)
    shell = ShellTools(config.workspace, config.command_timeout)
    memory = MemoryManager(config.storage / "memory.json")
    checkpoint = CheckpointManager(config.workspace, config.storage / "checkpoints", config.max_checkpoints)
    registry = ToolRegistry(filesystem, shell, checkpoint)
    context = ContextManager(SYSTEM_PROMPT, config.workspace, config.context_window, memory.as_context())
    safety = SafetyPolicy(config.workspace, config.blocked_commands, config.confirm_commands, config.safety_mode)
    llm = LLMClient(config.model, config.api_key, config.base_url)
    return AgentLoop(llm, registry, context, config.max_rounds, print_event,
                     safety=safety, checkpoint=checkpoint, memory=memory, confirm=confirm_operation)


def confirm_operation(prompt: str) -> bool:
    try:
        return input(f"\n[需要授权]\n{prompt}\n允许执行？[y/N] ").strip().lower() in {"y", "yes"}
    except (EOFError, KeyboardInterrupt):
        return False


def main() -> None:
    try:
        agent = build_agent(Config.from_env())
    except (ValueError, RuntimeError) as exc:
        raise SystemExit(f"启动失败：{exc}") from exc
    print("Coding Agent 已启动。输入编程任务，或输入 exit/quit 退出。")
    while True:
        try:
            task = input("\n任务> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见。")
            break
        if task.lower() in {"exit", "quit"}:
            break
        if task:
            try:
                agent.run(task)
            except Exception as exc:
                print(f"\n[运行错误]\n{type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
