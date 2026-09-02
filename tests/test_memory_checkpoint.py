from pathlib import Path

from agent.checkpoint import CheckpointManager
from agent.memory import MemoryManager


def test_memory_is_persistent_and_deduplicated(tmp_path: Path):
    path = tmp_path / "storage" / "memory.json"
    memory = MemoryManager(path)
    memory.remember("important_files", "app.py")
    memory.remember("important_files", "app.py")
    memory.remember("commands", {"test": "pytest"})

    restored = MemoryManager(path)
    assert restored.recall("important_files") == ["app.py"]
    assert restored.recall("commands") == {"test": "pytest"}
    assert "app.py" in restored.as_context()


def test_checkpoint_can_restore_and_prunes_history(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    file = workspace / "app.py"
    file.write_text("version 1", encoding="utf-8")
    manager = CheckpointManager(workspace, tmp_path / "checkpoints", max_checkpoints=1)

    checkpoint = manager.create_checkpoint("before edit")
    file.write_text("version 2", encoding="utf-8")
    manager.rollback(checkpoint)
    assert file.read_text(encoding="utf-8") == "version 1"

    manager.create_checkpoint("next")
    assert len(manager.list_checkpoints()) == 1
