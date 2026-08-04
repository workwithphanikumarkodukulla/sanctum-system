"""Workspace inspection tool."""
from __future__ import annotations
import os
from pathlib import Path
from typing import Any
from app.config import Config
from app.tools.base import BaseTool
class WorkspaceTool(BaseTool):
    """Inspect the workspace structure and files."""
    name = "workspace"
    description = "Inspect or interact with the workspace."
    def __init__(self, root_dir: str | os.PathLike[str] | None = None) -> None:
        super().__init__()
        workspace_root = root_dir if root_dir is not None else Config.WORKSPACE
        self.root_dir = Path(workspace_root).expanduser().resolve()
        self.root_dir.mkdir(parents=True, exist_ok=True)
    def execute(self, *args, **kwargs) -> Any:
        action = kwargs.pop("action", None)
        if action is None and args:
            action = args[0]
            args = args[1:]
        if action == "list_files":
            return self.list_files(*args, **kwargs)
        if action == "tree":
            return self.tree(*args, **kwargs)
        if action == "stat":
            return self.stat(*args, **kwargs)
        raise ValueError("Unsupported workspace action. Use list_files, tree, or stat.")
    def list_files(self, path: str = ".", recursive: bool = False) -> dict[str, Any]:
        target = self._resolve_path(path)
        if not target.exists():
            raise FileNotFoundError(f"Path not found: {target}")
        if not target.is_dir():
            raise NotADirectoryError(f"Path is not a directory: {target}")
        if recursive:
            items = [
                str(item.relative_to(self.root_dir))
                for item in [item for item in target.rglob("*") if item.exists()]
            ]
        else:
            items = [
                str(item.relative_to(self.root_dir))
                for item in [item for item in target.iterdir() if item.exists()]
            ]
        return {"action": "list_files", "path": str(target), "items": sorted(items)}
    def tree(self, path: str = ".", max_depth: int = 3) -> dict[str, Any]:
        target = self._resolve_path(path)
        if not target.exists():
            raise FileNotFoundError(f"Path not found: {target}")
        if not target.is_dir():
            raise NotADirectoryError(f"Path is not a directory: {target}")
        return {
            "action": "tree",
            "path": str(target),
            "items": self._build_tree(target, current_depth=0, max_depth=max_depth),
        }
    def stat(self, path: str) -> dict[str, Any]:
        target = self._resolve_path(path)
        if not target.exists():
            raise FileNotFoundError(f"Path not found: {target}")
        info = target.stat()
        return {
            "action": "stat",
            "path": str(target),
            "is_file": target.is_file(),
            "is_dir": target.is_dir(),
            "size": info.st_size,
            "modified_time": info.st_mtime,
        }
    def _build_tree(self, path: Path, current_depth: int, max_depth: int) -> list[dict[str, Any]]:
        if current_depth >= max_depth:
            return []
        entries: list[dict[str, Any]] = []
        for item in sorted(path.iterdir(), key=lambda candidate: (candidate.is_file(), candidate.name.lower())):
            entry = {
                "name": item.name,
                "path": str(item.relative_to(self.root_dir)),
                "type": "directory" if item.is_dir() else "file",
            }
            if item.is_dir():
                entry["children"] = self._build_tree(item, current_depth + 1, max_depth)
            entries.append(entry)
        return entries
    def _resolve_path(self, path: str) -> Path:
        candidate = (self.root_dir / path).expanduser().resolve()
        try:
            candidate.relative_to(self.root_dir)
        except ValueError as exc:
            raise ValueError("Path escapes the configured workspace root.") from exc
        return candidate
