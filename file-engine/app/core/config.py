"""Application configuration and environment settings."""
import os
import shutil
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    HOST: str = "0.0.0.0"
    PORT: int = 8001
    DEBUG: bool = False
    MAX_UPLOAD_SIZE_BYTES: int = 100 * 1024 * 1024  # 100 MB default max upload limit

    # OCR confidence routing boundaries (heuristic routing signals, NOT calibrated probabilities of correctness)
    CONFIDENCE_THRESHOLD: float = 0.80
    RECHECK_CONFIDENCE: float = 0.85
    CRITICAL_REGION_THRESHOLD: float = 0.85
    CONSENSUS_HIGH_CONFIDENCE: float = 0.96
    CONSENSUS_LOW_CONFIDENCE: float = 0.30
    HANDWRITING_SUSPECTED_THRESHOLD: float = 0.68
    HANDWRITING_PRINTED_THRESHOLD: float = 0.82
    HANDWRITING_VLM_REREAD_THRESHOLD: float = 0.75
    TESSERACT_CMD: str | None = os.getenv(
        "TESSERACT_CMD", shutil.which("tesseract") or "/opt/homebrew/bin/tesseract"
    )
    ENABLE_PADDLE_OCR: bool = os.getenv("ENABLE_PADDLE_OCR", "false").lower() in ("true", "1")

    # Local Ollama multimodal escalation
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    OLLAMA_VISION_MODEL: str = os.getenv("OLLAMA_VISION_MODEL", "qwen3-vl:8b")
    OLLAMA_TIMEOUT_SECONDS: float = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "60.0"))
    OLLAMA_AUTO_UNLOAD: bool = True


settings = Settings()
