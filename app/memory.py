"""Memory module — in-session message history for LangChain context.

Session-level history is kept in-memory for LangChain messages.
Long-term persistence is delegated to WorkspaceHistoryManager.
"""
import json
from pathlib import Path
from app.logger import logger
from app.config import Config


class MemoryManager:
    """Manages in-session conversation history for LangChain context building."""

    def __init__(self):
        self._history = []
        # Legacy: still maintain a global history.json for backward compat
        workspace = Path(Config.WORKSPACE)
        workspace.mkdir(exist_ok=True)
        self._history_file = workspace / "history.json"
        self._load_history()

    def add_user_message(self, message: str) -> None:
        self._history.append({"role": "user", "content": message})
        self._save_history()

    def add_ai_message(self, message: str) -> None:
        self._history.append({"role": "assistant", "content": message})
        self._save_history()

    def get_history(self) -> list[dict[str, str]]:
        return list(self._history)

    def clear(self) -> None:
        self._history.clear()
        self._save_history()
        logger.info("Conversation history cleared.")

    def _load_history(self) -> None:
        if not self._history_file.exists():
            self._history = []
            self._save_history()
            logger.info("New conversation history created.")
            return
        try:
            with self._history_file.open("r", encoding="utf-8") as file:
                self._history = json.load(file)
            logger.info("Conversation history loaded successfully.")
        except Exception:
            logger.exception("Failed to load conversation history.")
            self._history = []

    def _save_history(self) -> None:
        try:
            with self._history_file.open("w", encoding="utf-8") as file:
                json.dump(self._history, file, ensure_ascii=False, indent=4)
        except Exception:
            logger.exception("Failed to save conversation history.")
# Developer Note :-
#
# Dear Memory...
#
# Please remember everything.
#
# Except my bugs.
#
# Those should disappear automatically. 😁😂✌️
#
# If you forget the user's messages...
#
# Please don't call yourself "MemoryManager" anymore. 😅
