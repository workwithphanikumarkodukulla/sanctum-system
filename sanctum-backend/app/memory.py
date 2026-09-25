"""Memory module — in-session message history for LangChain context.

Session-level history is kept in-memory for LangChain messages.
Long-term persistence is delegated to WorkspaceHistoryManager.
"""
import json
import re
from pathlib import Path
from typing import Any
from app.logger import logger
from app.config import Config


class MemoryManager:
    """Manages in-session conversation history and ChatGPT-style memory context."""

    def __init__(self, workspace_dir: str | Path | None = None):
        self._history: list[dict[str, str]] = []
        self.user_name: str = ""
        self.facts: list[str] = []
        self.preferences: list[str] = []
        self.projects: list[str] = []
        workspace = Path(workspace_dir) if workspace_dir else Path(Config.WORKSPACE)
        workspace.mkdir(exist_ok=True)
        self._history_file = workspace / "history.json"
        self._load_history()

    def extract_memories(self, message: str) -> dict[str, Any]:
        """Extract user identity, preferences, ongoing projects, and facts from user messages."""
        msg_clean = message.strip()
        updates: dict[str, Any] = {"name": "", "facts": [], "preferences": [], "projects": []}

        # 1. User Name
        m_name = re.search(
            r"\b(?:my\s+name\s+(?:is\s+)?|i\s+am\s+|call\s+me\s+)([A-Z][a-zA-Z0-9_\-]+|[a-z][a-zA-Z0-9_\-]+)\b",
            msg_clean,
            re.IGNORECASE,
        )
        if m_name:
            cand = m_name.group(1).strip()
            if cand.lower() not in (
                "a", "an", "the", "not", "here", "ready", "trying", "asking",
                "wondering", "looking", "testing", "doing", "working", "sanctum",
                "building", "interested", "planning"
            ):
                self.user_name = cand.capitalize()
                updates["name"] = self.user_name

        # 2. Preferences & Interests
        for p in [
            r"\b(?:i\s+love|i\s+like|i\s+prefer)\s+([^.,;!?\n]+)",
            r"\b(?:my\s+favorite\s+[^.,;!?\n]+is)\s+([^.,;!?\n]+)",
            r"\b(?:always\s+(?:use|include|do))\s+([^.,;!?\n]+)",
        ]:
            for m in re.finditer(p, msg_clean, re.IGNORECASE):
                fact = m.group(0).strip()
                if len(fact) > 5 and not any(k in fact.lower() for k in ("to ask", "to know", "to see", "to understand", "to make sure")):
                    if not any(fact.lower() in existing.lower() or existing.lower() in fact.lower() for existing in self.preferences):
                        self.preferences.append(fact)
                        updates["preferences"].append(fact)

        # 3. Projects & Work
        for p in [
            r"\b(?:i\s+am\s+working\s+on|i\'m\s+working\s+on|i\s+work\s+on|i\s+am\s+building|i\'m\s+building|my\s+project\s+is|our\s+project\s+is)\s+([^.,;!?\n]+)",
            r"\b(?:we\s+are\s+developing|i\s+am\s+developing|developing\s+a)\s+([^.,;!?\n]+)",
        ]:
            for m in re.finditer(p, msg_clean, re.IGNORECASE):
                fact = m.group(0).strip()
                if len(fact) > 5:
                    if not any(fact.lower() in existing.lower() or existing.lower() in fact.lower() for existing in self.projects):
                        self.projects.append(fact)
                        updates["projects"].append(fact)

        # 4. Explicit Memory Directives & User Facts
        for p in [
            r"\b(?:remember\s+(?:that\s+)?|keep\s+in\s+mind\s+(?:that\s+)?|note\s+that\s+)([^.,;!?\n]+)",
            r"\b(?:i\s+live\s+in|i\s+am\s+from|i\s+study\s+at|i\s+work\s+at)\s+([^.,;!?\n]+)",
        ]:
            for m in re.finditer(p, msg_clean, re.IGNORECASE):
                fact = m.group(1).strip()
                if len(fact) > 3:
                    if not any(fact.lower() in existing.lower() or existing.lower() in fact.lower() for existing in self.facts):
                        self.facts.append(fact)
                        updates["facts"].append(fact)

        self.preferences = self.preferences[-15:]
        self.projects = self.projects[-15:]
        self.facts = self.facts[-20:]

        return updates

    def search_relevant_history(self, query: str, top_k: int = 4) -> list[dict[str, str]]:
        """Search previous conversation history using token overlap (conversational RAG)."""
        if not self._history or len(self._history) <= 1:
            return []

        stopwords = {
            "what", "is", "my", "the", "and", "in", "am", "i", "a", "an", "to",
            "for", "of", "on", "with", "at", "by", "do", "you", "remember", "did",
            "tell", "say", "talk", "we", "our", "about", "me", "are", "can", "how"
        }
        q_words = set(re.findall(r"\w+", query.lower())) - stopwords
        if not q_words:
            return []

        scored = []
        for idx, turn in enumerate(self._history[:-1]):
            content = turn.get("content", "")
            if not content:
                continue
            t_words = set(re.findall(r"\w+", content.lower()))
            overlap = q_words & t_words
            if overlap:
                scored.append((len(overlap), idx, turn))

        scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
        return [item[2] for item in scored[:top_k]]

    def get_memory_context(self, query: str = "") -> str:
        """Construct a ChatGPT-style Memory & Context block for system prompt injection."""
        sections: list[str] = []

        profile_lines: list[str] = []
        if self.user_name:
            profile_lines.append(f"• User Name: {self.user_name}")
        for proj in self.projects:
            profile_lines.append(f"• Project / Work Focus: {proj}")
        for pref in self.preferences:
            profile_lines.append(f"• User Preference / Interest: {pref}")
        for fact in self.facts:
            profile_lines.append(f"• Retained User Fact: {fact}")

        if profile_lines:
            sections.append(
                "[CHATGPT-STYLE MEMORY & STORED USER CONTEXT]\n"
                "The following context and facts have been remembered from previous conversations:\n"
                + "\n".join(profile_lines)
                + "\nAlways reference and respect these details when answering the user."
            )

        is_recall_query = bool(re.search(
            r"\b(recall|remember|earlier|previous|what\s+did\s+(?:i|we)|what\s+was\s+the|who\s+am\s+i|my\s+name|do\s+you\s+(?:know|remember)\s+my)\b",
            query,
            re.IGNORECASE,
        ))
        if query and is_recall_query:
            relevant_turns = self.search_relevant_history(query, top_k=3)
            if relevant_turns:
                turn_lines: list[str] = []
                for turn in relevant_turns:
                    role_label = "User" if turn.get("role") == "user" else "Assistant"
                    snippet = turn.get("content", "").replace("\n", " ").strip()
                    if len(snippet) > 200:
                        snippet = snippet[:200] + "..."
                    turn_lines.append(f"• {role_label} said earlier: \"{snippet}\"")
                sections.append(
                    "[RELEVANT CONVERSATIONAL MEMORY / RETRIEVED PAST TURNS]\n"
                    + "\n".join(turn_lines)
                )

        return "\n\n".join(sections)

    def add_user_message(self, message: str) -> None:
        self._history.append({"role": "user", "content": message})
        self.extract_memories(message)
        self._save_history()

    def add_ai_message(self, message: str, model: str = "", duration_s: float | None = None) -> None:
        entry: dict[str, Any] = {"role": "assistant", "content": message}
        if model:
            entry["model"] = model
        if duration_s is not None:
            entry["duration"] = f"{duration_s:.1f}s"
        self._history.append(entry)
        self._save_history()

    def get_history(self) -> list[dict[str, str]]:
        return list(self._history)

    def clear(self) -> None:
        self._history.clear()
        self.user_name = ""
        self.facts.clear()
        self.preferences.clear()
        self.projects.clear()
        self._save_history()
        logger.info("Conversation history and memory store cleared.")

    def _load_history(self) -> None:
        if not self._history_file.exists():
            self._history = []
            self._save_history()
            logger.info("New conversation history created.")
            return
        try:
            from app.sovereign_vault import read_sovereign_text
            text, _ = read_sovereign_text(self._history_file)
            data = json.loads(text)
            if isinstance(data, list):
                self._history = data
                for item in self._history:
                    if item.get("role") == "user":
                        self.extract_memories(item.get("content", ""))
            elif isinstance(data, dict):
                self._history = data.get("messages", [])
                self.user_name = data.get("user_name", "")
                self.facts = data.get("facts", [])
                self.preferences = data.get("preferences", [])
                self.projects = data.get("projects", [])
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
