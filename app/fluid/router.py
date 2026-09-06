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

_ROUTING_RULES: list[tuple[str, list[str]]] = [
    ("docs", [
        r"\b(summary|summarize|tldr|recap|synopsis|overview|outline|abstract)\b",
        r"\b(doc(s|ument)?|report|readme|guide|manual|tutorial|note|essay|article|letter|memo|speech|paper|wiki|specification|spec)\b",
        r"\b(write|create|generate)\s+(?:a\s+)?(?:report|doc|docs|guide|manual|tutorial|note|paper|letter|essay|pdf|docx?|dox|excel|xlsx|csv|spreadsheet|presentation|pptx)\b",
        r"\b(pdf|docx?|dox|excel|xlsx|csv|spreadsheet|presentation|powerpoint|pptx|deck|slides?)\b",
        r"\b(big\s+pdf|the\s+pdf|in\s+the\s+pdf|query.*pdf|read.*pdf|inspect.*pdf)\b",
        r"\b(handnotes|handwriting|handwritten)\b",
    ]),
    ("code", [
        r"\b(write|create|make|generate|save|debug|fix|refactor|implement)\s+(?:a\s+)?(?:python|py|javascript|js|typescript|ts|java|html|css|script|program|function|endpoint|api)\b",
        r"\b(python|javascript|typescript|golang|rust|cpp|html|css|bash|shell|sql|regex|syntax|algorithm|recursion|pointer)\b",
        r"\b(def|class\s+[A-Za-z0-9_]+|function|import|return|cout|printf|console\.log)\b",
        r"\b(unit\s*test|pytest|refactor|compile|stack\s*trace)\b",
        r"\.(py|js|ts|java|cpp|c|go|rs|rb|cs|php|html|css|sql|sh|bash)\b",
        r"```",
    ]),
    ("reasoning", [
        r"\b(reason|explain\s+why|analyze|evaluate|compare|pros\s+and\s+cons|decision|tradeoff|logic|deduce|infer|hypothesis|proof|argument|calculate|math|equation|formula|step\s+by\s+step|solve|solvee|root|roots|derivative|differentiate|diff|integral|integrate|limit)\b",
    ]),
    ("vision", [
        r"\b(image|photo|picture|screenshot|diagram|chart|graph|visual|look\s+at|analyze\s+this\s+image|describe\s+the\s+image)\b",
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
        incompatible = ("deepseek-coder", "vl", "vision", "llava")
        tool_compatible = [m for m in available if not any(inc in m.lower() for inc in incompatible)]
        candidates = tool_compatible if tool_compatible else available

        best = self._registry.best_model_for(category, candidates)
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
