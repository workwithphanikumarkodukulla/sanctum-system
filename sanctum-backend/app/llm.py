"""Local-only model management for OpenAI-compatible inference servers."""
from __future__ import annotations

import json
from urllib.parse import urlparse
from urllib.error import URLError
from urllib.request import Request, urlopen

from langchain_openai import ChatOpenAI
from app.config import Config
from app.logger import logger


class LLMManager:
    def __init__(self):
        self.base_url = Config.LOCAL_LLM_BASE_URL.rstrip("/")
        hostname = urlparse(self.base_url).hostname
        if hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("LOCAL_LLM_BASE_URL must point to loopback infrastructure.")
        self.model_name = Config.LOCAL_LLM_MODEL or "local-model"
        self._llm = ChatOpenAI(
            model=self.model_name,
            temperature=0,
            api_key=Config.LOCAL_LLM_API_KEY,
            base_url=self.base_url,
            timeout=Config.LOCAL_LLM_TIMEOUT,
            max_retries=1,
            max_tokens=2048,
        )
        logger.info("Local LLM initialized: {} ({})", self.model_name, self.base_url)
    def invoke(self, prompt):
        return self._llm.invoke(prompt)
    def stream(self, prompt):
        return self._llm.stream(prompt)
    def health_check(self):
        try:
            models = self.list_models()
            healthy = bool(models)
            logger.info("Local LLM health check: {}", "passed" if healthy else "no models")
            return healthy
        except Exception:
            logger.exception("Local LLM health check failed.")
            return False

    def list_models(self):
        """Discover models from the local OpenAI-compatible server."""
        request = Request(f"{self.base_url}/models", headers={"Accept": "application/json"})
        try:
            with urlopen(request, timeout=3) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (OSError, URLError, ValueError):
            return []
        model_items = payload.get("data") or []
        return [item.get("id") for item in model_items if item.get("id")]

    def select_for_task(self, task):
        """Use local model metadata and task hints to select a suitable model."""
        models = self.list_models()
        if not models:
            return self.model_name
        # Models like deepseek-coder:6.7b and vision models (qwen3-vl) do not support function calling in Ollama
        incompatible = ("deepseek-coder", "vl", "vision", "llava")
        lowered = task.lower()
        hints = ([("coding", ("qwen2.5-coder",)),
                  ("reasoning", ("qwq", "thinking"))])
        for role, words in hints:
            if any(word in lowered for word in words):
                match = next((model for model in models if any(word in model.lower() for word in words) and not any(inc in model.lower() for inc in incompatible)), None)
                if match and match != self.model_name:
                    self.change_model(match)
                    return match
        if self.model_name not in models or any(inc in self.model_name.lower() for inc in incompatible):
            default_candidate = next((m for m in models if "gemma" in m.lower()), None)
            if not default_candidate:
                default_candidate = next((m for m in models if not any(inc in m.lower() for inc in incompatible)), models[0])
            self.change_model(default_candidate)
        return self.model_name

    def change_model(self, model_name):
        self.model_name = model_name
        self._llm = ChatOpenAI(
            model=self.model_name,
            temperature=0,
            api_key=Config.LOCAL_LLM_API_KEY,
            base_url=self.base_url,
            timeout=Config.LOCAL_LLM_TIMEOUT,
            max_retries=1,
            max_tokens=2048,
        )
        logger.info("Local model changed to '{}'.", self.model_name)

    def get_model_info(self):
        return {
            "provider": "Local OpenAI-compatible",
            "model": self.model_name,
            "base_url": self.base_url,
            "network_scope": "loopback only",
            "temperature": 0,
        }
