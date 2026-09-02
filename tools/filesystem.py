"""Filesystem operations used by the agent."""

from __future__ import annotations

from pathlib import Path


class FileSystemTools:
    def __init__(self, workspace: Path):
        self.workspace = workspace.resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)

    def _path(self, path: str) -> Path:
        candidate = (self.workspace / path).resolve()
        # Workspace confinement is a correctness boundary for relative tool paths.
        if candidate != self.workspace and self.workspace not in candidate.parents:
            raise ValueError(f"Path is outside workspace: {path}")
        return candidate

    def list_files(self, path: str = ".") -> str:
        target = self._path(path)
        if not target.exists():
            raise FileNotFoundError(path)
        if not target.is_dir():
            raise NotADirectoryError(path)
        entries = sorted(target.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower()))
        return "\n".join(f"{item.name}/" if item.is_dir() else item.name for item in entries) or "(empty)"

    def read_file(self, path: str) -> str:
        return self._path(path).read_text(encoding="utf-8")

    def write_file(self, path: str, content: str) -> str:
        target = self._path(path)
        if target.exists():
            raise FileExistsError(f"File already exists; use edit_file: {path}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"Created {path} ({len(content)} characters)."

    def edit_file(self, path: str, old_text: str, new_text: str) -> str:
        target = self._path(path)
        content = target.read_text(encoding="utf-8")
        occurrences = content.count(old_text)
        if occurrences == 0:
            raise ValueError("old_text was not found in the file.")
        if occurrences > 1:
            raise ValueError(f"old_text occurs {occurrences} times; provide more context.")
        target.write_text(content.replace(old_text, new_text, 1), encoding="utf-8")
        return f"Updated {path}."

    def search_text(self, query: str, path: str = ".") -> str:
        target = self._path(path)
        files = [target] if target.is_file() else (item for item in target.rglob("*") if item.is_file())
        matches: list[str] = []
        for file in files:
            try:
                for number, line in enumerate(file.read_text(encoding="utf-8").splitlines(), 1):
                    if query in line:
                        relative = file.relative_to(self.workspace).as_posix()
                        matches.append(f"{relative}:{number}: {line}")
            except (UnicodeDecodeError, OSError):
                continue
        return "\n".join(matches) or "No matches found."
