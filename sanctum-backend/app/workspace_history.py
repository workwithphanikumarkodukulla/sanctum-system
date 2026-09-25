"""Per-workspace isolated conversation history.

Each workspace stores its own .sanctum/history.json so that switching
workspaces instantly restores prior context without re-scanning files.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.logger import logger

MAX_HISTORY_TURNS = 200  # keep last N messages per workspace


class WorkspaceHistoryManager:
    """Manages isolated conversation history for a single workspace root."""

    def __init__(self, workspace_root: str | Path) -> None:
        self._root = Path(workspace_root).expanduser().resolve()
        self._sanctum_dir = self._root / ".sanctum"
        self._sanctum_dir.mkdir(parents=True, exist_ok=True)
        self._history_file = self._sanctum_dir / "history.json"
        self._profile_file = self._sanctum_dir / "profile.json"
        self._history: list[dict[str, Any]] = []
        self._load()
        self._ensure_profile()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_message(self, role: str, content: str, metadata: dict | None = None) -> None:
        """Append a message to workspace history."""
        entry: dict[str, Any] = {
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if metadata:
            entry["metadata"] = metadata
        self._history.append(entry)
        # Trim to MAX_HISTORY_TURNS
        if len(self._history) > MAX_HISTORY_TURNS:
            self._history = self._history[-MAX_HISTORY_TURNS:]
        self._save()

    def get_recent(self, n: int = 50) -> list[dict[str, Any]]:
        """Return the last n messages."""
        return list(self._history[-n:])

    def get_summary(self) -> str:
        """Return a compressed context summary for injection into system prompt."""
        if not self._history:
            return ""
        user_msgs = [e for e in self._history if e["role"] == "user"]
        if not user_msgs:
            return ""
        recent = user_msgs[-5:]
        topics = [m["content"][:100].replace("\n", " ") for m in recent]
        summary = "\n".join(f"- {t}" for t in topics)
        return (
            f"[WORKSPACE HISTORY — {len(self._history)} messages]\n"
            f"Prior workspace topics (for background reference only; do NOT answer or repeat these unless asked in the current message):\n{summary}\n"
        )

    def get_all(self) -> list[dict[str, Any]]:
        return list(self._history)

    def clear(self) -> None:
        self._history = []
        self._save()
        logger.info("Workspace history cleared for {}", self._root)

    def workspace_root(self) -> str:
        return str(self._root)

    def profile(self) -> dict[str, Any]:
        """Return workspace profile metadata."""
        if self._profile_file.exists():
            try:
                return json.loads(self._profile_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if not self._history_file.exists():
            self._history = []
            self._save()
            logger.info("New workspace history created at {}", self._history_file)
            return
        try:
            data = json.loads(self._history_file.read_text(encoding="utf-8"))
            self._history = data if isinstance(data, list) else []
            logger.info("Workspace history loaded: {} messages from {}", len(self._history), self._root)
        except Exception:
            logger.exception("Failed to load workspace history from {}", self._history_file)
            self._history = []

    def _save(self) -> None:
        try:
            self._history_file.write_text(
                json.dumps(self._history, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            logger.exception("Failed to save workspace history.")

    def _ensure_profile(self) -> None:
        if self._profile_file.exists():
            return
        profile = {
            "name": self._root.name,
            "path": str(self._root),
            "created": datetime.now(timezone.utc).isoformat(),
            "description": "",
        }
        try:
            self._profile_file.write_text(
                json.dumps(profile, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            logger.exception("Failed to create workspace profile.")
