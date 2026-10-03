"""
Settings and configuration for AI Outreach Platform v2.

Loads environment variables with OUTREACH_ prefix.
"""

import logging
import os
from typing import List

from pydantic_settings import BaseSettings

_INSECURE_JWT_SECRET = "change-me-in-production-use-strong-random-key"


class Settings(BaseSettings):
    APP_NAME: str = "AI Outreach Platform"
    APP_VERSION: str = "2.0.0"
    APP_DESCRIPTION: str = "Metadata-driven AI-powered outreach automation"

    API_PREFIX: str = "/api"
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8080"]

    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "outreach_ai"

    REDIS_URL: str = "redis://localhost:6379/0"

    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    LLM_PROVIDER: str = "nvidia"
    NVIDIA_NIM_API_KEY: str = ""
    NVIDIA_NIM_MODEL: str = "moonshotai/kimi-k2.6"

    XIAOMI_API_KEY: str = ""
    XIAOMI_MODEL: str = "mimo-v2.5"

    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemma-4-26b-a4b-it"

    APOLLO_API_KEY: str = ""
    HUNTER_API_KEY: str = ""
    TAVILY_API_KEY: str = ""
    FIRECRAWL_API_KEY: str = ""

    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/gmail/callback"

    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_URL: str = ""
    QDRANT_API_KEY: str = ""
    QDRANT_COLLECTION: str = "outreach"

    JWT_SECRET: str = _INSECURE_JWT_SECRET
    COOKIE_ENCRYPTION_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24
    JWT_EXPIRATION_MINUTES: int = 1440

    EMAIL_FROM: str = "noreply@outreach.ai"
    DEBUG: bool = False
    BACKEND_URL: str = "http://localhost:8000"
    FRONTEND_URL: str = "http://localhost:3000"
    RATE_LIMIT_PER_MINUTE: int = 300
    LINKEDIN_HEADLESS: bool = False
    DISABLE_LOCAL_SCHEDULER: bool = False

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()


def _validate_jwt_secret(cfg: Settings) -> None:
    """Refuse to run with a known/weak JWT secret (it also seeds the Fernet key)."""
    weak = cfg.JWT_SECRET == _INSECURE_JWT_SECRET or len(cfg.JWT_SECRET) < 32
    if not weak:
        return
    msg = (
        "JWT_SECRET is unset, default, or shorter than 32 chars. Set a strong random "
        "value in .env (e.g. `python -c \"import secrets; print(secrets.token_urlsafe(64))\"`)."
    )
    if cfg.DEBUG:
        logging.getLogger(__name__).warning("INSECURE CONFIG (DEBUG only): %s", msg)
        return
    raise RuntimeError(msg)


_validate_jwt_secret(settings)
