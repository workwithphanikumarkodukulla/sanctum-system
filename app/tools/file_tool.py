"""Workspace file operations for the agent."""
from __future__ import annotations
import os
from pathlib import Path
from typing import Any
from app.config import Config
from app.tools.base import BaseTool
class FileTool(BaseTool):
	"""Create, read, update, delete, and rename files inside the workspace."""
	name = "file"
	description = "Work with files in the configured workspace."
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
		if action == "create_file":
			return self.create_file(*args, **kwargs)
		if action == "read_file":
			return self.read_file(*args, **kwargs)
		if action == "write_file":
			return self.write_file(*args, **kwargs)
		if action == "delete_file":
			return self.delete_file(*args, **kwargs)
		if action == "rename_file":
			return self.rename_file(*args, **kwargs)
		raise ValueError("Unsupported file action. Use create_file, read_file, write_file, delete_file, or rename_file.")
	def create_file(self, path: str, content: str = "") -> dict[str, Any]:
		file_path = self._resolve_path(path)
		if file_path.exists():
			raise FileExistsError(f"File already exists: {file_path}")
		file_path.parent.mkdir(parents=True, exist_ok=True)
		file_path.write_text(content, encoding="utf-8")
		return {"action": "create_file", "path": str(file_path), "created": True}
	def read_file(
		self,
		path: str,
		start_line: int | None = None,
		end_line: int | None = None,
	) -> dict[str, Any]:
		file_path = self._resolve_path(path)
		if not file_path.exists():
			raise FileNotFoundError(f"File not found: {file_path}")
		if not file_path.is_file():
			raise IsADirectoryError(f"Path is not a file: {file_path}")
		try:
			text = file_path.read_text(encoding="utf-8")
		except UnicodeDecodeError:
			raise ValueError(f"File '{path}' appears to be a binary file, not valid UTF-8 text. Use 'read_document' for documents or images.")

		lines = text.splitlines()
		max_lines_limit = 2000
		if start_line is None and end_line is None:
			if len(lines) > max_lines_limit:
				truncated_lines = lines[:max_lines_limit]
				return {
					"action": "read_file",
					"path": str(file_path),
					"total_lines": len(lines),
					"lines_shown": max_lines_limit,
					"truncated": True,
					"notice": f"File exceeds {max_lines_limit} lines. Truncated to avoid context overflow.",
					"content": "\n".join(truncated_lines) + f"\n\n[... Truncated: showing first {max_lines_limit} of {len(lines)} lines to protect LLM context ...]",
				}
			return {"action": "read_file", "path": str(file_path), "content": text}
		start_index = 1 if start_line is None else max(start_line, 1)
		end_index = len(lines) if end_line is None else max(end_line, 0)
		if end_index < start_index:
			raise ValueError("end_line must be greater than or equal to start_line.")
		selected_lines = lines[start_index - 1 : end_index]
		return {
			"action": "read_file",
			"path": str(file_path),
			"start_line": start_index,
			"end_line": end_index,
			"content": "\n".join(selected_lines),
		}
	def write_file(self, path: str, content: str) -> dict[str, Any]:
		file_path = self._resolve_path(path)
		file_path.parent.mkdir(parents=True, exist_ok=True)
		file_path.write_text(content, encoding="utf-8")
		return {"action": "write_file", "path": str(file_path), "written": True}
	def delete_file(self, path: str) -> dict[str, Any]:
		file_path = self._resolve_path(path)
		if not file_path.exists():
			raise FileNotFoundError(f"File not found: {file_path}")
		if not file_path.is_file():
			raise IsADirectoryError(f"Path is not a file: {file_path}")
		file_path.unlink()
		return {"action": "delete_file", "path": str(file_path), "deleted": True}
	def rename_file(self, old_path: str, new_path: str) -> dict[str, Any]:
		source_path = self._resolve_path(old_path)
		target_path = self._resolve_path(new_path)
		if not source_path.exists():
			raise FileNotFoundError(f"File not found: {source_path}")
		if target_path.exists():
			raise FileExistsError(f"Target already exists: {target_path}")
		target_path.parent.mkdir(parents=True, exist_ok=True)
		source_path.rename(target_path)
		return {
			"action": "rename_file",
			"old_path": str(source_path),
			"new_path": str(target_path),
			"renamed": True,
		}
	def _resolve_path(self, path: str) -> Path:
		if path is None or not str(path).strip():
			raise ValueError("Path cannot be empty or whitespace.")
		if "\x00" in str(path):
			raise ValueError("Path contains invalid null byte.")
		try:
			candidate = (self.root_dir / path).expanduser().resolve()
			candidate.relative_to(self.root_dir)
		except ValueError as exc:
			raise ValueError("Path escapes the configured workspace root.") from exc
		return candidate

