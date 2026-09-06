"""Workspace inspection tool."""
from __future__ import annotations
import os
import re
from fnmatch import fnmatch
from pathlib import Path
from typing import Any
from app.config import Config
from app.tools.base import BaseTool
class WorkspaceTool(BaseTool):
    """Inspect the workspace structure and files."""
    name = "workspace"
    description = "Inspect or interact with the workspace."

    EXCLUDED_DIRS = {
        ".git",
        ".pytest_cache",
        "__pycache__",
        ".venv",
        "venv",
        "node_modules",
        ".cache",
        ".mypy_cache",
        ".tox",
    }

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
        if action == "find_files":
            return self.find_files(*args, **kwargs)
        raise ValueError("Unsupported workspace action. Use list_files, tree, stat, or find_files.")

    def list_files(self, path: str = ".", recursive: bool = False) -> dict[str, Any]:
        target = self._resolve_path(path)
        if not target.exists():
            raise FileNotFoundError(f"Path not found: {target}")
        if not target.is_dir():
            raise NotADirectoryError(f"Path is not a directory: {target}")
        if recursive:
            items = []
            for root, dirs, files in os.walk(target):
                dirs[:] = [d for d in dirs if d not in self.EXCLUDED_DIRS]
                for d in dirs:
                    p = Path(root) / d
                    items.append(str(p.relative_to(self.root_dir)))
                for f in files:
                    p = Path(root) / f
                    items.append(str(p.relative_to(self.root_dir)))
        else:
            items = [
                str(item.relative_to(self.root_dir))
                for item in target.iterdir()
                if item.exists() and item.name not in self.EXCLUDED_DIRS
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

    def find_files(self, pattern: str = "*", path: str = ".") -> dict[str, Any]:
        """Find files matching a glob pattern or keyword substring across the workspace."""
        target = self._resolve_path(path)
        if not target.exists():
            raise FileNotFoundError(f"Path not found: {target}")
        if not target.is_dir():
            raise NotADirectoryError(f"Path is not a directory: {target}")

        clean_pattern = pattern.strip()
        # Support OR-separated search terms (e.g. "expenditure OR finance OR report" or "csr | mrpl")
        sub_terms = [t.strip() for t in re.split(r"\s+\bOR\b\s+|\|", clean_pattern, flags=re.IGNORECASE) if t.strip()]
        if not sub_terms:
            sub_terms = [clean_pattern]

        active_excluded = {d for d in self.EXCLUDED_DIRS if d not in pattern}
        matches: list[dict[str, Any]] = []

        for root, dirs, files in os.walk(target):
            dirs[:] = [d for d in dirs if d not in active_excluded]
            dirs.sort()
            for file_name in sorted(files):
                item = Path(root) / file_name
                rel_path = str(item.relative_to(self.root_dir))

                matched = False
                for term in sub_terms:
                    term_has_glob = any(char in term for char in ("*", "?", "[", "]"))
                    if term_has_glob:
                        if fnmatch(file_name.lower(), term.lower()) or fnmatch(rel_path.lower(), term.lower()):
                            matched = True
                            break
                    else:
                        if term.lower() in file_name.lower() or term.lower() in rel_path.lower():
                            matched = True
                            break

                if matched:
                    matches.append({
                        "path": rel_path,
                        "filename": file_name,
                        "size_bytes": item.stat().st_size,
                        "extension": item.suffix.lower(),
                    })

        # Fallback for natural language descriptions (e.g. "CSR report", "BloodLink presentation")
        if not matches and not any(char in clean_pattern for char in ("*", "?", "[", "]")):
            words = [w.strip() for w in re.split(r"[\s,]+", clean_pattern) if len(w.strip()) >= 3 and w.lower() not in ("the", "for", "and", "file", "document", "docs")]
            if words:
                for root, dirs, files in os.walk(target):
                    dirs[:] = [d for d in dirs if d not in active_excluded]
                    dirs.sort()
                    for file_name in sorted(files):
                        item = Path(root) / file_name
                        rel_path = str(item.relative_to(self.root_dir))
                        if any(w.lower() in file_name.lower() or w.lower() in rel_path.lower() for w in words):
                            matches.append({
                                "path": rel_path,
                                "filename": file_name,
                                "size_bytes": item.stat().st_size,
                                "extension": item.suffix.lower(),
                            })

        return {
            "action": "find_files",
            "pattern": pattern,
            "path": str(target),
            "matches": matches,
            "count": len(matches),
        }

    def _build_tree(self, path: Path, current_depth: int, max_depth: int) -> list[dict[str, Any]]:
        if current_depth >= max_depth:
            return []
        entries: list[dict[str, Any]] = []
        for item in sorted(path.iterdir(), key=lambda candidate: (candidate.is_file(), candidate.name.lower())):
            if item.name in self.EXCLUDED_DIRS:
                continue
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
        if path is None or not str(path).strip():
            return self.root_dir
        if "\x00" in str(path):
            raise ValueError("Path contains invalid null byte.")
        try:
            candidate = (self.root_dir / path).expanduser().resolve()
            candidate.relative_to(self.root_dir)
        except ValueError as exc:
            raise ValueError("Path escapes the configured workspace root.") from exc
        return candidate

