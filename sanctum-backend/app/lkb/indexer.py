"""LKB Indexer — Chunks and indexes documents for the Local Knowledge Base.

Each workspace has its own isolated index under .sanctum/knowledge/.
Uses TF-IDF for search (fully offline, no external downloads).
"""
from __future__ import annotations

import json
import pickle
import re
from pathlib import Path
from typing import Any

from app.logger import logger

# Supported file extensions for text extraction
SUPPORTED_EXTENSIONS = {
    ".txt", ".md", ".py", ".js", ".ts", ".java", ".c", ".cpp", ".go",
    ".rs", ".rb", ".cs", ".php", ".html", ".css", ".json", ".yaml",
    ".yml", ".toml", ".ini", ".cfg", ".sh", ".bash", ".sql", ".xml",
    ".rst", ".tex", ".csv",
}

CHUNK_SIZE = 400  # tokens (approx words)
CHUNK_OVERLAP = 50


class LKBIndexer:
    """Indexes workspace files into the local TF-IDF knowledge base."""

    def __init__(self, knowledge_dir: Path) -> None:
        self._dir = knowledge_dir
        self._dir.mkdir(parents=True, exist_ok=True)
        self._index_file = self._dir / "index.json"
        self._vectors_file = self._dir / "tfidf_vectors.pkl"
        self._index: dict[str, Any] = self._load_index()
        self._vectorizer = None
        self._matrix = None
        self._chunk_texts: list[str] = []
        self._chunk_meta: list[dict] = []
        self._load_vectors()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def index_file(self, file_path: str, workspace_root: Path) -> dict[str, Any]:
        """Index a single file. Returns stats dict."""
        path = Path(file_path)
        if not path.is_absolute():
            path = workspace_root / path
        path = path.resolve()

        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            return {"status": "skipped", "reason": f"Unsupported extension: {path.suffix}"}

        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            return {"status": "error", "error": str(e)}

        rel_path = str(path.relative_to(workspace_root)) if path.is_relative_to(workspace_root) else str(path)
        chunks = self._chunk_text(text)

        self._index[rel_path] = {
            "path": rel_path,
            "abs_path": str(path),
            "chunks": len(chunks),
            "size": path.stat().st_size,
            "extension": path.suffix,
        }
        self._save_index()

        # Rebuild vectors with all indexed content
        self._rebuild_vectors()
        return {"status": "indexed", "path": rel_path, "chunks": len(chunks)}

    def index_directory(self, dir_path: str, workspace_root: Path, recursive: bool = True) -> dict[str, Any]:
        """Index all supported files in a directory."""
        path = Path(dir_path)
        if not path.is_absolute():
            path = workspace_root / path
        path = path.resolve()

        pattern = "**/*" if recursive else "*"
        files = [f for f in path.glob(pattern) if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS]
        results = []
        for f in files[:100]:  # cap at 100 files per batch
            results.append(self.index_file(str(f), workspace_root))

        return {"status": "done", "indexed": len([r for r in results if r.get("status") == "indexed"]), "total": len(files)}

    def list_indexed(self) -> list[dict[str, Any]]:
        return list(self._index.values())

    def clear(self) -> None:
        self._index = {}
        self._save_index()
        self._chunk_texts = []
        self._chunk_meta = []
        self._vectorizer = None
        self._matrix = None
        if self._vectors_file.exists():
            self._vectors_file.unlink()
        logger.info("LKB: index cleared")

    def get_chunks(self) -> tuple[list[str], list[dict]]:
        """Return all indexed chunks and their metadata for searching."""
        return self._chunk_texts, self._chunk_meta

    def has_content(self) -> bool:
        return bool(self._index)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _chunk_text(self, text: str) -> list[str]:
        """Split text into overlapping chunks."""
        words = text.split()
        chunks = []
        i = 0
        while i < len(words):
            chunk = " ".join(words[i: i + CHUNK_SIZE])
            chunks.append(chunk)
            i += CHUNK_SIZE - CHUNK_OVERLAP
        return chunks or [text]

    def _rebuild_vectors(self) -> None:
        """Rebuild TF-IDF matrix from all indexed documents."""
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
        except ImportError:
            logger.warning("LKB: scikit-learn not installed. Keyword search only.")
            return

        all_chunks: list[str] = []
        all_meta: list[dict] = []

        for rel_path, meta in self._index.items():
            abs_path = meta.get("abs_path", rel_path)
            try:
                text = Path(abs_path).read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            chunks = self._chunk_text(text)
            for i, chunk in enumerate(chunks):
                all_chunks.append(chunk)
                all_meta.append({"path": rel_path, "chunk_index": i})

        if not all_chunks:
            return

        self._vectorizer = TfidfVectorizer(max_features=10000, stop_words="english")
        self._matrix = self._vectorizer.fit_transform(all_chunks)
        self._chunk_texts = all_chunks
        self._chunk_meta = all_meta

        try:
            with self._vectors_file.open("wb") as f:
                pickle.dump({
                    "vectorizer": self._vectorizer,
                    "matrix": self._matrix,
                    "texts": self._chunk_texts,
                    "meta": self._chunk_meta,
                }, f)
        except Exception:
            logger.exception("LKB: failed to save vectors.")

    def _load_vectors(self) -> None:
        if not self._vectors_file.exists():
            return
        try:
            with self._vectors_file.open("rb") as f:
                data = pickle.load(f)
            self._vectorizer = data["vectorizer"]
            self._matrix = data["matrix"]
            self._chunk_texts = data["texts"]
            self._chunk_meta = data["meta"]
        except Exception:
            logger.exception("LKB: failed to load vectors.")

    def _load_index(self) -> dict[str, Any]:
        if not self._index_file.exists():
            return {}
        try:
            return json.loads(self._index_file.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save_index(self) -> None:
        try:
            self._index_file.write_text(
                json.dumps(self._index, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            logger.exception("LKB: failed to save index.")
