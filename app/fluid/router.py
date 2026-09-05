"""FluidRouter — Smart task-to-model request router.

Classifies incoming user messages into task categories and routes
each request to the best local model for that category.

If only one model is available, all tasks are handled by that model.
No model data is shared with or visible to any other model.
"""
from __future__ import annotations

import re
from typing import Any

from app.logger import logger
from app.fluid.model_registry import ModelRegistry
from app.fluid.model_profiler import ModelProfiler

# Task classification rules: (category, patterns)
_ROUTING_RULES: list[tuple[str, list[str]]] = [
    ("code", [
        r"\b(code|program|script|function|class|implement|debug|fix\s+bug|refactor|test|compile|syntax|algorithm|api|endpoint|module|library|import|loop|recursive|stack|queue|binary|sort|search)\b",
        r"\.(py|js|ts|java|cpp|c|go|rs|rb|cs|php|html|css|sql|sh|bash)\b",
        r"```",
    ]),
    ("vision", [
        r"\b(image|photo|picture|screenshot|diagram|chart|graph|visual|look\s+at|analyze\s+this\s+image|describe\s+the\s+image)\b",
    ]),
    ("reasoning", [
        r"\b(reason|explain\s+why|analyze|evaluate|compare|pros\s+and\s+cons|decision|tradeoff|logic|deduce|infer|hypothesis|proof|argument|calculate|math|equation|formula|step\s+by\s+step)\b",
    ]),
    ("docs", [
        r"\b(doc(s|ument)?|write|report|summary|summarize|readme|guide|manual|tutorial|note|essay|article|description|overview|explain|document|wiki|specification|spec)\b",
    ]),
]

_CATEGORY_LABELS = {
    "code": "Code Generation",
    "docs": "Documentation",
    "reasoning": "Analytical Reasoning",
    "vision": "Vision/Multimodal",
    "general": "General Purpose",
}


class FluidRouter:
    """Routes user requests to the most capable local model per task type."""

    def __init__(self, registry: ModelRegistry, profiler: ModelProfiler, llm_manager) -> None:
        self._registry = registry
        self._profiler = profiler
        self._llm_manager = llm_manager
        self._known_models: set[str] = set()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def route(self, task: str) -> str:
        """Select the best model for this task. Returns model name."""
        available = self._llm_manager.list_models()
        if not available:
            return self._llm_manager.model_name

        # Detect and profile new models (async, non-blocking)
        self._detect_new_models(available)

        if len(available) == 1:
            # Only one model — handle everything
            model = available[0]
            if model != self._llm_manager.model_name:
                self._llm_manager.change_model(model)
            return model

        category = self.classify(task)
        best = self._registry.best_model_for(category, available)
        if best and best != self._llm_manager.model_name:
            self._llm_manager.change_model(best)
            logger.info("Fluid: routed '{}' task to model '{}'", category, best)
        return self._llm_manager.model_name

    def classify(self, task: str) -> str:
        """Classify a task string into a routing category."""
        lower = task.lower()
        for category, patterns in _ROUTING_RULES:
            if any(re.search(pattern, lower) for pattern in patterns):
                return category
        return "general"

    def preview_route(self, task: str) -> dict[str, Any]:
        """Preview routing decision without changing the active model."""
        available = self._llm_manager.list_models()
        category = self.classify(task)
        best = self._registry.best_model_for(category, available) if available else None
        return {
            "task": task,
            "category": category,
            "category_label": _CATEGORY_LABELS.get(category, category),
            "recommended_model": best,
            "available_models": available,
            "profiles": {
                m: self._registry.get_profile(m)
                for m in available
            },
        }

    def routing_table(self) -> list[dict[str, Any]]:
        """Return the full routing capability matrix for the UI."""
        available = self._llm_manager.list_models()
        rows = []
        for model in available:
            profile = self._registry.get_profile(model)
            rows.append({
                "model": model,
                "profiled": self._registry.is_profiled(model),
                "scores": profile,
                "best_for": max(
                    (k for k in profile if k != "_profiled"),
                    key=lambda k: profile.get(k, 0),
                    default="general",
                ),
            })
        return rows

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _detect_new_models(self, available: list[str]) -> None:
        """Profile any newly detected models in the background."""
        new_models = set(available) - self._known_models
        self._known_models = set(available)
        for model in new_models:
            if self._profiler.needs_profiling(model):
                logger.info("Fluid: new model detected '{}', profiling in background...", model)
                self._profiler.profile_async(model)
