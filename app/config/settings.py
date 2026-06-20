"""
Settings and configuration for AI Outreach Platform v2.

Loads environment variables with OUTREACH_ prefix.
"""

from pydantic_settings import BaseSettings
from typing import List
import os


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
    NVIDIA_NIM_MODEL: str = "qwen/qwen3.5-122b-a10b"

    XIAOMI_API_KEY: str = ""
    XIAOMI_MODEL: str = "mimo-v2.5"

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

    JWT_SECRET: str = "change-me-in-production-use-strong-random-key"
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

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()