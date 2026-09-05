"""Local Knowledge Base (LKB) package.

Each workspace maintains its own knowledge base under .sanctum/knowledge/.
No data leaks between workspaces.
"""
from app.lkb.manager import LKBManager

__all__ = ["LKBManager"]
