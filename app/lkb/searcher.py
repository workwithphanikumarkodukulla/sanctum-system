"""LKB Searcher — TF-IDF semantic search for the Local Knowledge Base."""
from __future__ import annotations

from typing import Any

from app.logger import logger


class LKBSearcher:
    """Searches the LKB index using TF-IDF cosine similarity."""

    def __init__(self, indexer) -> None:
        self._indexer = indexer

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Return top-k relevant chunks for a query."""
        if not query.strip():
            return []

        # Try TF-IDF search first
        results = self._tfidf_search(query, top_k)
        if results:
            return results

        # Fallback: keyword search
        return self._keyword_search(query, top_k)

    def search_for_context(self, query: str, max_tokens: int = 800) -> str:
        """Return a concatenated context string for LLM injection."""
        results = self.search(query, top_k=4)
        if not results:
            return ""

        parts = [f"[LKB: {r['path']}]\n{r['text'][:300]}" for r in results]
        context = "\n\n".join(parts)
        # Truncate to approximate token budget
        words = context.split()
        if len(words) > max_tokens:
            context = " ".join(words[:max_tokens]) + "..."
        return context

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _tfidf_search(self, query: str, top_k: int) -> list[dict[str, Any]]:
        chunks, meta = self._indexer.get_chunks()
        if not chunks:
            return []

        vectorizer = self._indexer._vectorizer
        matrix = self._indexer._matrix
        if vectorizer is None or matrix is None:
            return []

        try:
            import numpy as np
            query_vec = vectorizer.transform([query])
            # Cosine similarity: dot product of normalized vectors
            scores = (matrix @ query_vec.T).toarray().flatten()
            top_indices = scores.argsort()[::-1][:top_k]
            results = []
            for idx in top_indices:
                if scores[idx] < 0.01:
                    continue
                results.append({
                    "path": meta[idx]["path"],
                    "chunk_index": meta[idx]["chunk_index"],
                    "text": chunks[idx],
                    "score": float(scores[idx]),
                    "method": "tfidf",
                })
            return results
        except Exception:
            logger.exception("LKB: TF-IDF search failed.")
            return []

    def _keyword_search(self, query: str, top_k: int) -> list[dict[str, Any]]:
        """Simple keyword fallback when TF-IDF is unavailable."""
        chunks, meta = self._indexer.get_chunks()
        if not chunks:
            return []

        query_words = set(query.lower().split())
        scored = []
        for i, chunk in enumerate(chunks):
            chunk_words = set(chunk.lower().split())
            hits = len(query_words & chunk_words)
            if hits > 0:
                scored.append((i, hits / max(len(query_words), 1)))

        scored.sort(key=lambda x: x[1], reverse=True)
        results = []
        for idx, score in scored[:top_k]:
            results.append({
                "path": meta[idx]["path"],
                "chunk_index": meta[idx]["chunk_index"],
                "text": chunks[idx],
                "score": score,
                "method": "keyword",
            })
        return results
