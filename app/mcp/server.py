"""A small local MCP-style server boundary for approved workspace tools.

The transport is intentionally in-process today: the Flask API exposes the same
list/call contract, keeping tool execution local and making a stdio transport
straightforward to add for desktop packaging.
"""
from __future__ import annotations

from typing import Any


class LocalMCPServer:
    """Expose an allowlisted ToolManager through MCP-shaped operations."""

    protocol_version = "2025-06-18"

    def __init__(self, tool_manager):
        self.tool_manager = tool_manager

    def list_tools(self) -> list[dict[str, Any]]:
        tools = []
        for name in self.tool_manager.list_tools():
            tool = self.tool_manager.get(name)
            tools.append({
                "name": name,
                "description": getattr(tool, "description", name),
                "scope": "workspace-local",
            })
        return tools

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        return self.tool_manager.execute(name, **(arguments or {}))

    def server_info(self) -> dict[str, str]:
        return {
            "name": "sanctum-local-tools",
            "protocol_version": self.protocol_version,
            "transport": "in-process / localhost",
            "data_boundary": "workspace and local machine only",
        }
