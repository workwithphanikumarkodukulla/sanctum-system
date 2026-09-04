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
        lowered = task.lower()
        hints = ([("vision", ("vision", "vl", "llava")),
                  ("coding", ("code", "coder", "deepseek")),
                  ("reasoning", ("reason", "qwq", "thinking"))])
        for role, words in hints:
            if any(word in lowered for word in words):
                match = next((model for model in models if any(word in model.lower() for word in words)), None)
                if match:
                    self.change_model(match)
                    return match
        if self.model_name not in models:
            self.change_model(models[0])
        return self.model_name

    def change_model(self, model_name):
        self.model_name = model_name
        self._llm = ChatOpenAI(
            model=self.model_name,
            temperature=0,
            api_key=Config.LOCAL_LLM_API_KEY,
            base_url=self.base_url,
            timeout=Config.LOCAL_LLM_TIMEOUT,
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
