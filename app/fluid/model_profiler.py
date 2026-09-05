"""Model profiler for Sanctum Fluid Architecture.

When a new local model is detected, this module runs lightweight
benchmark prompts to score it across task dimensions.
Results are stored in the global ModelRegistry.

Benchmarks run in a background thread so they never block the UI.
"""
from __future__ import annotations

import threading
import time
from typing import Callable

from app.logger import logger
from app.fluid.model_registry import ModelRegistry

# Benchmark prompts per dimension
_BENCHMARKS: dict[str, dict] = {
    "code": {
        "prompt": "Write a Python function that reverses a string. Return only the code.",
        "good_signals": ["def ", "return", "[::-1]", "reverse"],
        "weight": 1.0,
    },
    "docs": {
        "prompt": "Write a one-paragraph professional summary about software testing best practices.",
        "good_signals": ["testing", "quality", "ensure", "software", "practice"],
        "weight": 1.0,
    },
    "reasoning": {
        "prompt": "If a train travels 60 km/h for 2 hours then 80 km/h for 1 hour, what is the total distance? Show your reasoning.",
        "good_signals": ["200", "120", "80", "km", "total"],
        "weight": 1.0,
    },
}

_VISION_KEYWORDS = ["vision", "vl", "llava", "minicpm", "bakllava", "moondream", "cogvlm"]


class ModelProfiler:
    """Benchmarks new models and stores results in the registry."""

    def __init__(self, registry: ModelRegistry, llm_manager) -> None:
        self._registry = registry
        self._llm_manager = llm_manager
        self._running: set[str] = set()
        self._lock = threading.Lock()
        self._profile_lock = threading.Lock()

    def needs_profiling(self, model_name: str) -> bool:
        return not self._registry.is_profiled(model_name)

    def profile_async(
        self,
        model_name: str,
        on_complete: Callable[[str, dict], None] | None = None,
    ) -> None:
        """Run profiling in a background thread. Safe to call at any time."""
        with self._lock:
            if model_name in self._running:
                return
            self._running.add(model_name)

        thread = threading.Thread(
            target=self._run_profile,
            args=(model_name, on_complete),
            daemon=True,
        )
        thread.start()

    def profile_sync(self, model_name: str) -> dict[str, float]:
        """Run profiling synchronously (blocks). Returns the profile."""
        return self._run_profile(model_name)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _run_profile(
        self,
        model_name: str,
        on_complete: Callable[[str, dict], None] | None = None,
    ) -> dict[str, float]:
        logger.info("Fluid: profiling model '{}'...", model_name)
        scores: dict[str, float] = {}

        self._profile_lock.acquire()
        try:
            # Save and switch to model being profiled
            original_model = self._llm_manager.model_name
            self._llm_manager.change_model(model_name)

            for dimension, bench in _BENCHMARKS.items():
                try:
                    start = time.monotonic()
                    response = self._llm_manager.invoke(bench["prompt"])
                    elapsed = time.monotonic() - start
                    text = (
                        response.content
                        if hasattr(response, "content")
                        else str(response)
                    ).lower()
                    # Score = signal hits / total signals, with speed bonus
                    hits = sum(1 for s in bench["good_signals"] if s.lower() in text)
                    accuracy = hits / len(bench["good_signals"])
                    # Speed penalty: >30s gets 0.2 penalty
                    speed_factor = max(0.0, 1.0 - max(0.0, elapsed - 30) / 60)
                    scores[dimension] = round(
                        min(1.0, accuracy * bench["weight"] * speed_factor + 0.1), 4
                    )
                    logger.info("Fluid: {} scored {:.2f} on '{}'", model_name, scores[dimension], dimension)
                except Exception:
                    logger.exception("Fluid: benchmark '{}' failed for model '{}'", dimension, model_name)
                    scores[dimension] = 0.3  # fallback score

            # Vision: detect from model name
            lower = model_name.lower()
            scores["vision"] = 0.85 if any(kw in lower for kw in _VISION_KEYWORDS) else 0.0

            # General = average of code + docs + reasoning
            scores["general"] = round(
                (scores.get("code", 0.5) + scores.get("docs", 0.5) + scores.get("reasoning", 0.5)) / 3,
                4,
            )

            self._registry.set_profile(model_name, scores)
            self._registry.mark_profiled(model_name)

            # Restore original model
            self._llm_manager.change_model(original_model)
            logger.info("Fluid: profiling complete for '{}' → {}", model_name, scores)

        except Exception:
            logger.exception("Fluid: profiling failed for model '{}'", model_name)
            scores = {"code": 0.5, "docs": 0.5, "reasoning": 0.5, "vision": 0.0, "general": 0.5}

        finally:
            self._profile_lock.release()
            with self._lock:
                self._running.discard(model_name)

        if on_complete:
            try:
                on_complete(model_name, scores)
            except Exception:
                pass

        return scores
