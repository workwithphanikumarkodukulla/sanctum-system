"""Global model capability registry.

Stores per-model capability scores (0.0–1.0) in ~/.sanctum/global_model_registry.json.
Each model is isolated — its capability profile is independent of others.

Capability dimensions:
  - code:      Code generation, completion, debugging
  - docs:      Documentation, report writing, summarization
  - reasoning: Analytical reasoning, step-by-step thinking
  - vision:    Multimodal image understanding (0.0 if not supported)
  - general:   General-purpose conversational tasks
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.logger import logger

GLOBAL_DIR = Path.home() / ".sanctum"
REGISTRY_FILE = GLOBAL_DIR / "global_model_registry.json"

# Default capability scores applied when a model is first seen and
# not yet profiled.  Scores are refined by ModelProfiler.
_DEFAULT_PROFILE: dict[str, float] = {
    "code": 0.5,
    "docs": 0.5,
    "reasoning": 0.5,
    "vision": 0.0,
    "general": 0.7,
}

# Heuristic boosts applied from model name keywords (pre-profiling)
_NAME_HINTS: list[tuple[list[str], dict[str, float]]] = [
    (["code", "coder", "deepseek", "starcoder", "codellama", "qwen.*coder"],
     {"code": 0.85, "docs": 0.5, "reasoning": 0.65, "general": 0.6}),
    (["reason", "qwq", "thinking", "r1"],
     {"reasoning": 0.9, "code": 0.65, "general": 0.75}),
    (["llava", "vision", "vl", "minicpm", "bakllava"],
     {"vision": 0.85, "general": 0.7}),
    (["mistral", "mixtral", "llama", "phi", "gemma", "falcon", "vicuna"],
     {"general": 0.8, "docs": 0.65}),
]


class ModelRegistry:
    """Thread-safe global store for model capability profiles."""

    def __init__(self) -> None:
        GLOBAL_DIR.mkdir(parents=True, exist_ok=True)
        self._registry: dict[str, dict[str, float]] = {}
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_profile(self, model_name: str) -> dict[str, float]:
        """Return capability profile for a model (with heuristic defaults)."""
        if model_name not in self._registry:
            self._registry[model_name] = self._heuristic_profile(model_name)
            self._save()
        return dict(self._registry[model_name])

    def set_profile(self, model_name: str, profile: dict[str, float]) -> None:
        """Store a profiled capability score set for a model."""
        self._registry[model_name] = {k: round(float(v), 4) for k, v in profile.items()}
        self._save()
        logger.info("Fluid: model profile updated for '{}'", model_name)

    def update_score(self, model_name: str, dimension: str, score: float) -> None:
        profile = self.get_profile(model_name)
        profile[dimension] = round(float(score), 4)
        self.set_profile(model_name, profile)

    def best_model_for(self, dimension: str, available_models: list[str]) -> str | None:
        """Return the model with the highest score for a given task dimension."""
        if not available_models:
            return None
        if len(available_models) == 1:
            return available_models[0]
        scored = [(m, self.get_profile(m).get(dimension, 0.5)) for m in available_models]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[0][0]

    def all_profiles(self) -> dict[str, dict[str, float]]:
        return dict(self._registry)

    def is_profiled(self, model_name: str) -> bool:
        """Return True if the model has been fully benchmarked (not just heuristic)."""
        profile = self._registry.get(model_name, {})
        return profile.get("_profiled", False)

    def mark_profiled(self, model_name: str) -> None:
        if model_name in self._registry:
            self._registry[model_name]["_profiled"] = True
            self._save()

    def remove_model(self, model_name: str) -> None:
        self._registry.pop(model_name, None)
        self._save()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _heuristic_profile(self, model_name: str) -> dict[str, float]:
        """Estimate capability scores from model name keywords."""
        import re
        profile = dict(_DEFAULT_PROFILE)
        lower = model_name.lower()
        for keywords, overrides in _NAME_HINTS:
            if any(re.search(kw, lower) for kw in keywords):
                profile.update(overrides)
                break
        return profile

    def _load(self) -> None:
        if not REGISTRY_FILE.exists():
            self._registry = {}
            return
        try:
            self._registry = json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
            logger.info("Fluid: loaded {} model profiles", len(self._registry))
        except Exception:
            logger.exception("Fluid: failed to load model registry.")
            self._registry = {}

    def _save(self) -> None:
        try:
            REGISTRY_FILE.write_text(
                json.dumps(self._registry, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            logger.exception("Fluid: failed to save model registry.")
