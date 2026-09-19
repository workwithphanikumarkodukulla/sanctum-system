"""Workspace isolation registry for Sanctum Fluid Architecture.

Tracks all workspaces that have been opened, their metadata, and ensures
that no workspace's data is accessible from another workspace's context.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.logger import logger

GLOBAL_DIR = Path.home() / ".sanctum"
WORKSPACE_REGISTRY_FILE = GLOBAL_DIR / "workspace_registry.json"


class WorkspaceRegistry:
    """Registry of all known workspaces with isolation metadata."""

    def __init__(self) -> None:
        GLOBAL_DIR.mkdir(parents=True, exist_ok=True)
        self._workspaces: dict[str, dict[str, Any]] = {}
        self._active: str | None = None
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register(self, workspace_path: str) -> dict[str, Any]:
        """Register or update a workspace entry."""
        path = str(Path(workspace_path).expanduser().resolve())
        if path not in self._workspaces:
            self._workspaces[path] = {
                "path": path,
                "name": Path(path).name,
                "first_opened": datetime.now(timezone.utc).isoformat(),
                "last_opened": datetime.now(timezone.utc).isoformat(),
                "message_count": 0,
            }
            logger.info("Fluid: new workspace registered: {}", path)
        else:
            self._workspaces[path]["last_opened"] = datetime.now(timezone.utc).isoformat()
        self._active = path
        self._save()
        return dict(self._workspaces[path])

    def set_active(self, workspace_path: str) -> None:
        self._active = str(Path(workspace_path).expanduser().resolve())

    def get_active(self) -> str | None:
        return self._active

    def increment_messages(self, workspace_path: str) -> None:
        path = str(Path(workspace_path).expanduser().resolve())
        if path in self._workspaces:
            self._workspaces[path]["message_count"] = (
                self._workspaces[path].get("message_count", 0) + 1
            )
            self._save()

    def list_workspaces(self) -> list[dict[str, Any]]:
        return list(self._workspaces.values())

    def get_workspace(self, path: str) -> dict[str, Any] | None:
        resolved = str(Path(path).expanduser().resolve())
        return self._workspaces.get(resolved)

    def remove_workspace(self, path: str) -> None:
        resolved = str(Path(path).expanduser().resolve())
        self._workspaces.pop(resolved, None)
        self._save()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if not WORKSPACE_REGISTRY_FILE.exists():
            self._workspaces = {}
            return
        try:
            self._workspaces = json.loads(
                WORKSPACE_REGISTRY_FILE.read_text(encoding="utf-8")
            )
        except Exception:
            logger.exception("Fluid: failed to load workspace registry.")
            self._workspaces = {}

    def _save(self) -> None:
        try:
            WORKSPACE_REGISTRY_FILE.write_text(
                json.dumps(self._workspaces, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            logger.exception("Fluid: failed to save workspace registry.")
