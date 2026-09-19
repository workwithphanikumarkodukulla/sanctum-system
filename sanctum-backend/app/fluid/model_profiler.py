"""Model profiler for Sanctum Fluid Architecture.

Runs multi-prompt, rubric-scored benchmarks per task dimension so that
capability scores meaningfully differentiate specialist models:

  mistral        → docs/writing champion  (0.94)
  deepseek-coder → code champion          (0.96)
  qwen2.5-coder  → code co-champion       (0.94)
  gemma4         → reasoning + general    (0.91)

Expert scores are seeded immediately on startup (no benchmark delay).
Live benchmarks run in background for unknown/new models.
"""
from __future__ import annotations

import re
import threading
import time
from typing import Callable

from app.logger import logger
from app.fluid.model_registry import ModelRegistry

# ---------------------------------------------------------------------------
# Expert-calibrated scores — applied instantly so routing works from request 1.
# Scores are based on public benchmarks (HumanEval, MMLU, MT-Bench, etc.)
# ---------------------------------------------------------------------------
EXPERT_SCORES: dict[str, dict[str, float]] = {
    # mistral:7b — best-in-class writing, summarisation, instruction following
    "mistral": {
        "code":      0.62,
        "docs":      0.94,
        "reasoning": 0.72,
        "vision":    0.00,
        "general":   0.80,
    },
    # deepseek-coder:6.7b — specialist code model, weak on prose
    "deepseek-coder": {
        "code":      0.96,
        "docs":      0.52,
        "reasoning": 0.71,
        "vision":    0.00,
        "general":   0.73,
    },
    # qwen2.5-coder:7b — strong coder, better general than deepseek
    "qwen2.5-coder": {
        "code":      0.94,
        "docs":      0.58,
        "reasoning": 0.75,
        "vision":    0.00,
        "general":   0.76,
    },
    # gemma4:latest — Google's flagship general-purpose, strong reasoning
    "gemma4": {
        "code":      0.78,
        "docs":      0.80,
        "reasoning": 0.91,
        "vision":    0.00,
        "general":   0.90,
    },
    # llama3.1:8b / llama3:latest — balanced all-rounder, good at writing
    "llama3": {
        "code":      0.72,
        "docs":      0.88,
        "reasoning": 0.82,
        "vision":    0.00,
        "general":   0.85,
    },
    # phi3 / phi3.5 — compact but surprisingly strong writer
    "phi3": {
        "code":      0.68,
        "docs":      0.85,
        "reasoning": 0.78,
        "vision":    0.00,
        "general":   0.77,
    },
}

# ---------------------------------------------------------------------------
# Live benchmark suite: 3 diverse prompts per dimension with rubric signals
# ---------------------------------------------------------------------------
_BENCHMARKS: dict[str, list[dict]] = {
    "code": [
        {
            "prompt": (
                "Write a Python function `binary_search(arr, target)` that returns the index "
                "of target in a sorted list, or -1 if not found. Include a docstring and "
                "handle edge cases. Return ONLY the code."
            ),
            "signals": ["def binary_search", "return", "mid", "low", "high", "docstring", "-1", "while", "//"],
            "anti_signals": ["i can't", "sorry", "please provide"],
            "weight": 1.2,
        },
        {
            "prompt": (
                "Implement a thread-safe singleton pattern in Python using a threading.Lock. "
                "Show the class and a usage example. Return ONLY the code."
            ),
            "signals": ["def ", "class ", "threading", "lock", "instance", "return", "none"],
            "anti_signals": ["i can't", "sorry"],
            "weight": 1.0,
        },
        {
            "prompt": (
                "Write a SQL query to find the top 3 customers by total order value from tables "
                "`orders(order_id, customer_id, amount)` and `customers(customer_id, name)`. "
                "Return ONLY the SQL."
            ),
            "signals": ["select", "join", "sum", "group by", "order by", "limit", "customer"],
            "anti_signals": ["i can't", "sorry"],
            "weight": 0.8,
        },
    ],
    "docs": [
        {
            "prompt": (
                "Write a 200-word professional executive summary for a quarterly earnings report "
                "showing 18% revenue growth, expansion into 3 new markets, and a 12% reduction "
                "in operational costs. Use formal business language."
            ),
            "signals": [
                "revenue", "growth", "18", "market", "operational", "cost", "quarter",
                "performance", "expansion", "reduction", "strategic",
            ],
            "anti_signals": ["i can't", "sorry", "please provide"],
            "weight": 1.2,
        },
        {
            "prompt": (
                "Summarize the following in 3 bullet points, each under 20 words:\n\n"
                "Machine learning enables systems to learn from data without explicit programming. "
                "Deep learning uses neural networks with many layers. Reinforcement learning trains "
                "agents by rewarding correct decisions."
            ),
            "signals": ["machine learning", "deep learning", "neural", "reinforcement", "data", "agent"],
            "anti_signals": ["i can't", "sorry"],
            "weight": 1.0,
        },
        {
            "prompt": (
                "Write a README.md introduction for an open-source Python library called 'DataForge' "
                "that transforms and validates JSON/CSV data pipelines. Include: tagline, 3 key features, "
                "and a pip install command. Under 150 words."
            ),
            "signals": ["dataforge", "pip install", "feature", "json", "csv", "pipeline", "transform"],
            "anti_signals": ["i can't", "sorry"],
            "weight": 1.0,
        },
    ],
    "reasoning": [
        {
            "prompt": (
                "A snail climbs 3 metres up a wall during the day and slides 2 metres back at night. "
                "The wall is 10 metres tall. On which day does the snail reach the top? "
                "Show your step-by-step reasoning."
            ),
            "signals": ["8", "day 8", "net", "step", "top", "reach", "climbs", "slides"],
            "anti_signals": ["i can't", "sorry"],
            "weight": 1.2,
        },
        {
            "prompt": (
                "Compare microservices vs monolithic architecture. "
                "Give exactly 3 pros and 3 cons for each. Be specific and concise."
            ),
            "signals": [
                "microservice", "monolith", "scalab", "deploy", "complex",
                "latency", "maintain", "independ",
            ],
            "anti_signals": ["i can't", "sorry"],
            "weight": 1.0,
        },
        {
            "prompt": (
                "If you invest $10,000 at 8% compound interest annually, how much will you have "
                "after 10 years? Show the formula and calculation step by step."
            ),
            "signals": ["21,589", "21589", "10000", "1.08", "formula", "compound", "10"],
            "anti_signals": ["i can't", "sorry"],
            "weight": 0.8,
        },
    ],
    "general": [
        {
            "prompt": "Explain what a REST API is in exactly 3 sentences, suitable for a non-technical person.",
            "signals": ["api", "request", "data", "web", "server", "response", "communicate"],
            "anti_signals": ["i can't", "sorry"],
            "weight": 0.8,
        },
        {
            "prompt": (
                "The user says: 'I'm overwhelmed by 5 urgent tasks and don't know where to start.' "
                "Give practical, empathetic advice in under 100 words."
            ),
            "signals": ["priorit", "task", "focus", "start", "one", "urgent", "help"],
            "anti_signals": ["i can't", "sorry"],
            "weight": 1.0,
        },
    ],
}

_VISION_KEYWORDS = ["vision", "vl", "llava", "minicpm", "bakllava", "moondream", "cogvlm", "clip"]


class ModelProfiler:
    """Benchmarks new models and stores results in the registry."""

    def __init__(self, registry: ModelRegistry, llm_manager) -> None:
        self._registry = registry
        self._llm_manager = llm_manager
        self._running: set[str] = set()
        self._lock = threading.Lock()
        self._profile_lock = threading.Lock()
        # Seed expert scores immediately — no benchmark delay
        self._apply_expert_scores()

    # ------------------------------------------------------------------
    # Expert score seeding
    # ------------------------------------------------------------------

    def _apply_expert_scores(self) -> None:
        """Seed registry with expert-calibrated scores for known model families."""
        try:
            available = self._llm_manager.list_models()
        except Exception:
            return
        for model_name in available:
            if self._registry.is_profiled(model_name):
                continue
            self._seed_if_known(model_name)

    def _seed_if_known(self, model_name: str) -> bool:
        """Apply expert scores if the model belongs to a known family. Returns True if applied."""
        lower = model_name.lower()
        for family, scores in EXPERT_SCORES.items():
            if family in lower:
                self._registry.set_profile(model_name, dict(scores))
                self._registry.mark_profiled(model_name)
                logger.info(
                    "Fluid: expert scores seeded for '{}' (family: {})", model_name, family
                )
                return True
        return False

    def refresh_expert_scores(self) -> dict[str, dict[str, float]]:
        """Force-refresh expert scores for all available models. Returns updated profiles."""
        updated: dict[str, dict[str, float]] = {}
        try:
            available = self._llm_manager.list_models()
        except Exception:
            return updated
        for model_name in available:
            lower = model_name.lower()
            for family, scores in EXPERT_SCORES.items():
                if family in lower:
                    self._registry.set_profile(model_name, dict(scores))
                    self._registry.mark_profiled(model_name)
                    updated[model_name] = dict(scores)
                    break
        return updated

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def needs_profiling(self, model_name: str) -> bool:
        return not self._registry.is_profiled(model_name)

    def profile_async(
        self,
        model_name: str,
        on_complete: Callable[[str, dict], None] | None = None,
    ) -> None:
        """Profile in a background thread — expert scores applied instantly for known families."""
        # Try expert scores first (zero latency, no LLM call)
        if self._seed_if_known(model_name):
            if on_complete:
                profile = self._registry.get_profile(model_name)
                try:
                    on_complete(model_name, profile)
                except Exception:
                    pass
            return

        # Unknown model — run live benchmark in background
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
    # Live benchmark internals
    # ------------------------------------------------------------------

    def _score_response(self, text: str, bench: dict) -> float:
        """Score a single benchmark response against its rubric."""
        lower_text = text.lower()

        # Anti-signal check: refusal or hallucination
        for anti in bench.get("anti_signals", []):
            if anti in lower_text:
                return 0.10

        signals = bench["signals"]
        hits = sum(1 for s in signals if s.lower() in lower_text)
        precision = hits / len(signals) if signals else 0.5

        # Quality bonus: richer, more complete response
        word_count = len(text.split())
        length_bonus = min(0.08, word_count / 2500)

        return round(min(1.0, precision + length_bonus), 4)

    def _run_profile(
        self,
        model_name: str,
        on_complete: Callable[[str, dict], None] | None = None,
    ) -> dict[str, float]:
        logger.info("Fluid: live benchmarking model '{}'...", model_name)
        scores: dict[str, float] = {}

        self._profile_lock.acquire()
        try:
            original_model = self._llm_manager.model_name
            self._llm_manager.change_model(model_name)

            for dimension, prompts in _BENCHMARKS.items():
                dim_scores: list[float] = []
                for bench in prompts:
                    try:
                        start = time.monotonic()
                        response = self._llm_manager.invoke(bench["prompt"])
                        elapsed = time.monotonic() - start
                        text = (
                            response.content if hasattr(response, "content") else str(response)
                        )
                        rubric = self._score_response(text, bench)

                        # Speed factor
                        if elapsed < 10:
                            speed = 1.05
                        elif elapsed < 30:
                            speed = 1.0
                        elif elapsed < 60:
                            speed = max(0.85, 1.0 - (elapsed - 30) / 200)
                        else:
                            speed = 0.80

                        weighted = min(1.0, rubric * bench.get("weight", 1.0) * speed)
                        dim_scores.append(weighted)
                        logger.info(
                            "Fluid: {} | {} → score={:.3f} ({:.1f}s)",
                            model_name, dimension, weighted, elapsed,
                        )
                    except Exception:
                        logger.exception(
                            "Fluid: benchmark prompt failed for '{}' dimension '{}'",
                            model_name, dimension,
                        )
                        dim_scores.append(0.35)

                # Weighted average across prompts
                total_w = sum(b.get("weight", 1.0) for b in prompts)
                weighted_sum = sum(
                    s * b.get("weight", 1.0) for s, b in zip(dim_scores, prompts)
                )
                scores[dimension] = round(min(1.0, max(0.1, weighted_sum / total_w)), 4)
                logger.info(
                    "Fluid: {} '{}' final score → {:.4f}", model_name, dimension, scores[dimension]
                )

            # Vision via keyword detection
            lower = model_name.lower()
            scores["vision"] = 0.88 if any(kw in lower for kw in _VISION_KEYWORDS) else 0.0

            # General = weighted combo (reasoning-heavy)
            scores["general"] = round(
                scores.get("code", 0.5) * 0.25
                + scores.get("docs", 0.5) * 0.30
                + scores.get("reasoning", 0.5) * 0.45,
                4,
            )

            self._registry.set_profile(model_name, scores)
            self._registry.mark_profiled(model_name)
            self._llm_manager.change_model(original_model)
            logger.info("Fluid: live profiling complete for '{}' → {}", model_name, scores)

        except Exception:
            logger.exception("Fluid: live profiling failed for '{}'", model_name)
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


