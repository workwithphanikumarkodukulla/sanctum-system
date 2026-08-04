"""Application configuration."""
import os
from dotenv import load_dotenv
load_dotenv()
class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"
    WORKSPACE = os.getenv("WORKSPACE", "workspace")
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL = os.getenv(
        "GROQ_MODEL",
        "llama-3.1-8b-instant"
    )
class DevelopmentConfig(Config):
    DEBUG = True
class ProductionConfig(Config):
    DEBUG = False
