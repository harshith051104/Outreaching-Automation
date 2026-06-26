"""
LLM Router for unified access to Groq models.

Provides fallback chain: llama-large -> llama-small -> qwen
"""

import logging
from typing import Callable, Any

logger = logging.getLogger(__name__)

HAS_GROQ = True

try:
    from groq import Groq
    from app.config.settings import settings
except ImportError:
    HAS_GROQ = False


class UnifiedLLMRouter:
    """Routes LLM requests to appropriate models with fallback."""

    MODEL_MAP = {
        "lead_discovery": "llama-3.3-70b-versatile",
        "research": "llama-3.3-70b-versatile",
        "signal_intelligence": "llama-3.3-70b-versatile",
        "opportunity": "llama-3.3-70b-versatile",
        "personalization": "llama-3.3-70b-versatile",
        "email_writing": "llama-3.3-70b-versatile",
        "reply_classification": "llama-3.3-70b-versatile",
        "followup": "llama-3.3-70b-versatile",
        "analytics": "llama-3.3-70b-versatile",
        "default": "llama-3.3-70b-versatile",
    }

    FALLBACK_CHAIN = [
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
    ]

    @classmethod
    def get_model(cls, role: str) -> str:
        if HAS_GROQ and settings.GROQ_MODEL:
            return settings.GROQ_MODEL
        return cls.MODEL_MAP.get(role, cls.MODEL_MAP["default"])

    @classmethod
    async def run_with_fallback(
        cls,
        role: str,
        client_call_func: Callable[[str], Any],
    ) -> str:
        from app.config.groq_config import get_llm_section_disabled
        
        # Map role to section
        section = "campaigns"
        if role in ("reply_classification", "followup"):
            section = "reply_monitor"
        elif role in ("lead_discovery", "research", "personalization", "email_writing"):
            section = "campaigns"
        elif role == "chatbot":
            section = "chatbot"
            
        if get_llm_section_disabled(section):
            logger.info(f"LLM is disabled for section '{section}'. Bypassing UnifiedLLMRouter.")
            return "{}"

        if not HAS_GROQ:
            return "{}"

        model = cls.get_model(role)
        attempts = []
        for m in [model] + cls.FALLBACK_CHAIN:
            if m not in attempts:
                attempts.append(m)

        import inspect
        for attempt_model in attempts:
            try:
                if inspect.iscoroutinefunction(client_call_func):
                    result = await client_call_func(attempt_model)
                else:
                    result = client_call_func(attempt_model)
                return result
            except Exception as e:
                logger.warning(f"Model {attempt_model} failed: {e}")
                continue

        return "{}"

    @classmethod
    def get_agno_model(cls, role: str):
        return cls.get_model(role)