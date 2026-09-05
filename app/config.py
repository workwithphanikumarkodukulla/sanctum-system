"""Application configuration."""
import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"
    WORKSPACE = os.getenv("WORKSPACE", "workspace")
    WORKSPACE_STATE_FILE = os.getenv("WORKSPACE_STATE_FILE", ".sanctum_workspace")
    # The default endpoint is Ollama on loopback. Any OpenAI-compatible local
    # server (LM Studio, llama.cpp, vLLM) can be selected with an environment variable.
    LOCAL_LLM_BASE_URL = os.getenv("LOCAL_LLM_BASE_URL", "http://127.0.0.1:11434/v1")
    LOCAL_LLM_API_KEY = os.getenv("LOCAL_LLM_API_KEY", "local-only")
    LOCAL_LLM_MODEL = os.getenv("LOCAL_LLM_MODEL", "")
    LOCAL_LLM_TIMEOUT = float(os.getenv("LOCAL_LLM_TIMEOUT", "120"))
    OFFLINE_MODE = os.getenv("OFFLINE_MODE", "true").lower() == "true"

    # Sanctum Fluid Architecture — global config directory
    SANCTUM_GLOBAL_DIR = Path.home() / ".sanctum"

    # LKB configuration
    LKB_CHUNK_SIZE = int(os.getenv("LKB_CHUNK_SIZE", "400"))
    LKB_TOP_K = int(os.getenv("LKB_TOP_K", "5"))


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
