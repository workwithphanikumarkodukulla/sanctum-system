"""Tool registry and execution helpers."""
from __future__ import annotations
from pathlib import Path
from typing import Any, Iterable
from app.tools.base import BaseTool
from app.tools.file_tool import FileTool
from app.tools.python_tool import PythonTool
from app.tools.terminal_tool import TerminalTool
from app.tools.workspace import WorkspaceTool
class ToolManager:
    """Register and execute tools by name."""
    def __init__(self, root_dir: str | None = None, register_defaults: bool = True) -> None:
        self._tools: dict[str, BaseTool] = {}
        if register_defaults:
            self.register_defaults(root_dir=root_dir)
    def register(self, tool: BaseTool) -> None:
        if not tool.name:
            raise ValueError("Tool name cannot be empty.")
        self._tools[tool.name] = tool
    def register_many(self, tools: Iterable[BaseTool]) -> None:
        for tool in tools:
            self.register(tool)
    def register_defaults(self, root_dir: str | None = None) -> None:
        self.register_many(
            [
                FileTool(root_dir=root_dir),
                PythonTool(root_dir=root_dir),
                TerminalTool(root_dir=root_dir),
                WorkspaceTool(root_dir=root_dir),
            ]
        )
    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)
    def get(self, name: str) -> BaseTool:
        if name not in self._tools:
            raise ValueError("Tool '{}' is not registered.".format(name))
        return self._tools[name]
    def has(self, name: str) -> bool:
        return name in self._tools
    def list_tools(self) -> list[str]:
        return sorted(self._tools)
    def execute(self, name: str, *args, **kwargs) -> Any:
        return self.get(name).execute(*args, **kwargs)

    def set_root_dir(self, root_dir: str) -> str:
        """Move every built-in workspace tool to one validated directory."""
        root = Path(root_dir).expanduser().resolve()
        if not root.exists() or not root.is_dir():
            raise ValueError("Workspace path must be an existing directory.")
        for tool in self._tools.values():
            if hasattr(tool, "root_dir"):
                tool.root_dir = root
        return str(root)
