"""Workspace snapshot and rollback support."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


class CheckpointManager:
    def __init__(self, workspace: Path, storage: Path, max_checkpoints: int = 5):
        self.workspace = workspace.resolve()
        self.storage = storage.resolve()
        self.max_checkpoints = max(1, max_checkpoints)
        self.storage.mkdir(parents=True, exist_ok=True)

    def create_checkpoint(self, reason: str = "workspace modification") -> str:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        destination = self.storage / stamp
        files = destination / "files"
        shutil.copytree(self.workspace, files)
        (destination / "metadata.json").write_text(
            json.dumps({"created_at": stamp, "reason": reason}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self._prune()
        return stamp

    def list_checkpoints(self) -> list[str]:
        return sorted((item.name for item in self.storage.iterdir() if item.is_dir()), reverse=True)

    def rollback(self, checkpoint_id: str | None = None) -> str:
        available = self.list_checkpoints()
        if not available:
            raise FileNotFoundError("No checkpoint is available.")
        selected = checkpoint_id or available[0]
        source = self.storage / selected / "files"
        if selected not in available or not source.is_dir():
            raise FileNotFoundError(f"Unknown checkpoint: {selected}")
        for item in self.workspace.iterdir():
            shutil.rmtree(item) if item.is_dir() else item.unlink()
        for item in source.iterdir():
            destination = self.workspace / item.name
            shutil.copytree(item, destination) if item.is_dir() else shutil.copy2(item, destination)
        return f"Rolled back workspace to checkpoint {selected}."

    def _prune(self) -> None:
        for checkpoint in self.list_checkpoints()[self.max_checkpoints:]:
            shutil.rmtree(self.storage / checkpoint)
