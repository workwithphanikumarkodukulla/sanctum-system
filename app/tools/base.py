"""Shared base classes for app tools."""
from __future__ import annotations
class BaseTool:
    """Common interface for tools registered with the agent."""
    name = ""
    description = ""
    def __init__(self, name: str | None = None, description: str | None = None) -> None:
        self.name = name if name is not None else getattr(type(self), "name", "")
        self.description = (
            description if description is not None else getattr(type(self), "description", "")
        )
    def execute(self, *args, **kwargs):
        raise NotImplementedError
