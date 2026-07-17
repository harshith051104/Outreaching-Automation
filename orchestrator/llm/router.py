import logging
import asyncio
import random
import time
from typing import Dict, Any, List, Optional
from orchestrator.llm.adapters import GroqAdapter, GeminiAdapter, GemmaAdapter, BaseLLMAdapter

logger = logging.getLogger(__name__)

# Task type routing config mapping to standard models
TASK_ROUTING_CONFIG = {
    "PLANNING": {
        "provider": "groq",
        "model": "llama-3.3-70b-versatile",
        "fallback_provider": "gemini",
        "fallback_model": "gemini-1.5-pro-latest"
    },
    "EMAIL_GENERATION": {
        "provider": "groq",
        "model": "llama-3.3-70b-versatile",
        "fallback_provider": "gemini",
        "fallback_model": "gemini-1.5-flash-latest"
    },
    "email_personalization": {
        "provider": "groq",
        "model": "llama-3.3-70b-versatile",
        "fallback_provider": "gemini",
        "fallback_model": "gemma-4-26b-a4b-it"
    },
    "default": {
        "provider": "groq",
        "model": "llama-3.3-70b-versatile",
        "fallback_provider": "gemini",
        "fallback_model": "gemini-1.5-flash-latest"
    }
}

class ProviderRouter:
    """Routes LLM inference tasks to the correct adapter, managing fallbacks, retries, and rate limits."""
    def __init__(self):
        self._adapters: Dict[str, BaseLLMAdapter] = {
            "groq": GroqAdapter(),
            "gemini": GeminiAdapter(),
            "gemma": GemmaAdapter()
        }

    async def route_and_generate(
        self,
        task_type: str,
        messages: List[Dict[str, str]],
        user_id: str,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        retry_strategy: str = "EXPONENTIAL_JITTER",
        max_attempts: int = 3,
        backoff_delay: float = 1.0
    ) -> Dict[str, Any]:
        route = TASK_ROUTING_CONFIG.get(task_type, TASK_ROUTING_CONFIG["default"])
        
        provider = route["provider"]
        model = route["model"]
        fallback_provider = route.get("fallback_provider")
        fallback_model = route.get("fallback_model")
        
        try:
            return await self._generate_with_retry(
                provider, model, messages, temperature, max_tokens, user_id,
                retry_strategy, max_attempts, backoff_delay
            )
        except Exception as e:
            if retry_strategy == "PROVIDER_FALLBACK" or (fallback_provider and fallback_model):
                logger.warning(f"ProviderRouter: Primary provider '{provider}' failed. Routing to fallback '{fallback_provider}'...")
                try:
                    return await self._generate_with_retry(
                        fallback_provider, fallback_model, messages, temperature, max_tokens, user_id,
                        retry_strategy, max_attempts, backoff_delay
                    )
                except Exception as fe:
                    logger.error(f"ProviderRouter: Fallback provider '{fallback_provider}' also failed: {fe}")
                    raise RuntimeError(f"LLM routing failed. Primary: {e}, Fallback: {fe}") from fe
            raise e

    async def _generate_with_retry(
        self,
        provider: str,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        user_id: str,
        retry_strategy: str,
        max_attempts: int,
        backoff_delay: float
    ) -> Dict[str, Any]:
        adapter = self._adapters.get(provider.lower())
        if not adapter:
            # Fallback to groq if provider not explicitly mapped
            adapter = self._adapters["groq"]
            provider = "groq"
            
        attempt = 0
        while attempt < max_attempts:
            try:
                return await adapter.generate(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    user_id=user_id
                )
            except Exception as e:
                attempt += 1
                if attempt >= max_attempts or retry_strategy == "NONE":
                    raise e
                
                # Apply retry delay strategies
                sleep_time = backoff_delay
                if retry_strategy == "FIXED":
                    sleep_time = backoff_delay
                elif retry_strategy == "EXPONENTIAL":
                    sleep_time = backoff_delay * (2 ** (attempt - 1))
                elif retry_strategy == "EXPONENTIAL_JITTER":
                    sleep_time = (backoff_delay * (2 ** (attempt - 1))) * (0.5 + random.random())
                
                logger.warning(f"ProviderRouter: Retry attempt {attempt} for '{provider}' after failure: {e}. Waiting {sleep_time:.2f}s...")
                await asyncio.sleep(sleep_time)
