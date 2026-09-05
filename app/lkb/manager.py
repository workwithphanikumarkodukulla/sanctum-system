"""LKB Manager — High-level API for the Local Knowledge Base.

Coordinates indexing, searching, and context retrieval for a workspace.
Each manager instance is scoped to a single workspace directory.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from app.lkb.indexer import LKBIndexer
from app.lkb.searcher import LKBSearcher
from app.logger import logger


class LKBManager:
    """Top-level knowledge base API for a workspace."""

    def __init__(self, workspace_root: str | Path) -> None:
        self._root = Path(workspace_root).expanduser().resolve()
        self._knowledge_dir = self._root / ".sanctum" / "knowledge"
        self._knowledge_dir.mkdir(parents=True, exist_ok=True)
        self._indexer = LKBIndexer(self._knowledge_dir)
        self._searcher = LKBSearcher(self._indexer)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def index_file(self, path: str) -> dict[str, Any]:
        """Index a file into the workspace knowledge base."""
        result = self._indexer.index_file(path, self._root)
        logger.info("LKB: indexed '{}' → {}", path, result.get("status"))
        return result

    def index_directory(self, path: str, recursive: bool = True) -> dict[str, Any]:
        """Index all supported files in a directory."""
        return self._indexer.index_directory(path, self._root, recursive=recursive)

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Search the knowledge base and return relevant chunks."""
        return self._searcher.search(query, top_k=top_k)

    def get_context(self, query: str) -> str:
        """Return a formatted context string for LLM injection."""
        return self._searcher.search_for_context(query)

    def list_indexed(self) -> list[dict[str, Any]]:
        """List all indexed files."""
        return self._indexer.list_indexed()

    def clear(self) -> None:
        """Clear the entire knowledge base for this workspace."""
        self._indexer.clear()

    def has_content(self) -> bool:
        return self._indexer.has_content()

    def set_workspace(self, new_root: str | Path) -> None:
        """Switch to a new workspace (rebuilds indexer)."""
        self._root = Path(new_root).expanduser().resolve()
        self._knowledge_dir = self._root / ".sanctum" / "knowledge"
        self._knowledge_dir.mkdir(parents=True, exist_ok=True)
        self._indexer = LKBIndexer(self._knowledge_dir)
        self._searcher = LKBSearcher(self._indexer)
        logger.info("LKB: switched to workspace '{}'", self._root)
