"""Command execution in the configured workspace."""

from __future__ import annotations

import subprocess
from pathlib import Path


class ShellTools:
    def __init__(self, workspace: Path, timeout: int = 120):
        self.workspace = workspace.resolve()
        self.timeout = timeout

    def run_command(self, command: str) -> str:
        try:
            result = subprocess.run(
                command,
                cwd=self.workspace,
                shell=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired as exc:
            return f"Command timed out after {self.timeout}s.\nstdout:\n{exc.stdout or ''}\nstderr:\n{exc.stderr or ''}"
        return (
            f"Exit code: {result.returncode}\n"
            f"stdout:\n{result.stdout or '(empty)'}\n"
            f"stderr:\n{result.stderr or '(empty)'}"
        )
