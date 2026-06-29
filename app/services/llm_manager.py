"""
LLM Manager & Model Router.

Provides unified, robust, and optimized access to Groq, Nvidia NIM, and Xiaomi providers.
Features automatic task-based routing, rate-limit backoff with jitter, provider fallbacks,
token accounting, and caching.
"""

import asyncio
import logging
import json
import time
import random
import hashlib
from typing import Any, List, Dict, Optional, Tuple
from datetime import datetime, timezone

from app.config.settings import settings
from app.config.mongodb_config import get_database

logger = logging.getLogger(__name__)

# Task type to default model/provider mappings
TASK_ROUTING = {
    "PLANNING": {
        "provider": "nvidia",
        "model": "nvidia/nemotron-3-ultra-550b-a55b",
        "fallback_provider": "groq",
        "fallback_model": "llama-3.3-70b-versatile"
    },
    "EMAIL_GENERATION": {
        "provider": "nvidia",
        "model": "moonshotai/kimi-k2.6",
        "fallback_provider": "groq",
        "fallback_model": "llama-3.3-70b-versatile"
    },
    "LINKEDIN_MESSAGE_GENERATION": {
        "provider": "nvidia",
        "model": "moonshotai/kimi-k2.6",
        "fallback_provider": "groq",
        "fallback_model": "llama-3.3-70b-versatile"
    },
    "CAMPAIGN_ANALYTICS": {
        "provider": "nvidia",
        "model": "meta/llama-3.3-70b-instruct",
        "fallback_provider": "groq",
        "fallback_model": "llama-3.3-70b-versatile"
    },
    "FAST_CHAT_RESPONSES": {
        "provider": "groq",
        "model": "llama-3.3-70b-versatile",
        "fallback_provider": "nvidia",
        "fallback_model": "moonshotai/kimi-k2.6"
    },
    "INTENT_CLASSIFICATION": {
        "provider": "xiaomi",
        "model": "mimo-v2.5",
        "fallback_provider": "groq",
        "fallback_model": "llama-3.3-70b-versatile"
    }
}


class LLMManager:
    """Centralized LLM service manager with rate limiting, retries, and caching."""

    _semaphores: Dict[str, asyncio.Semaphore] = {
        "nvidia": asyncio.Semaphore(3),  # Max 3 concurrent calls
        "groq": asyncio.Semaphore(5),    # Max 5 concurrent calls
        "xiaomi": asyncio.Semaphore(2),  # Max 2 concurrent calls
    }
    
    # In-memory payload cache to avoid redundant generations
    _cache: Dict[str, Tuple[Dict[str, Any], float]] = {}  # key -> (result, expires_at)
    _cache_ttl: float = 3600.0  # 1 hour default cache TTL

    @classmethod
    def _generate_cache_key(cls, messages: List[Dict], model: str, tools: Optional[List] = None) -> str:
        """Create a unique md5 hash key from the messages and model configurations."""
        serialized = json.dumps({
            "messages": messages,
            "model": model,
            "tools": tools
        }, sort_keys=True)
        return hashlib.md5(serialized.encode("utf-8")).hexdigest()

    @classmethod
    async def generate_completion(
        cls,
        task_type: str,
        messages: List[Dict[str, str]],
        user_id: str,
        temperature: float = 0.3,
        tools: Optional[List] = None,
        tool_choice: Optional[str] = None,
        bypass_cache: bool = False
    ) -> Dict[str, Any]:
        """
        Execute an LLM chat completion with dynamic routing, retries, backoff, and fallback.
        """
        # 1. Resolve task routing details
        route = TASK_ROUTING.get(task_type, {
            "provider": "groq",
            "model": "llama-3.3-70b-versatile",
            "fallback_provider": "groq",
            "fallback_model": "llama-3.1-8b-instant"
        })
        
        provider = route["provider"]
        model = route["model"]
        
        # 2. Check Cache
        cache_key = cls._generate_cache_key(messages, model, tools)
        if not bypass_cache and cache_key in cls._cache:
            result, expires_at = cls._cache[cache_key]
            if time.time() < expires_at:
                logger.info(f"LLMManager: Cache hit for task '{task_type}' using model '{model}'")
                await cls._log_metrics(task_type, model, provider, 0.0, 0, 0, cache_hit=True)
                return result

        # 3. Call with Retries and fallback
        start_time = time.time()
        try:
            result = await cls._execute_with_retry_and_fallback(
                task_type=task_type,
                messages=messages,
                provider=provider,
                model=model,
                fallback_provider=route.get("fallback_provider"),
                fallback_model=route.get("fallback_model"),
                user_id=user_id,
                temperature=temperature,
                tools=tools,
                tool_choice=tool_choice
            )
            
            # Cache successful response
            cls._cache[cache_key] = (result, time.time() + cls._cache_ttl)
            
            duration = time.time() - start_time
            # Simple token estimation for metrics
            prompt_tokens = sum(len(m.get("content", "")) for m in messages) // 4
            completion_tokens = len(result.get("content", "")) // 4
            await cls._log_metrics(task_type, model, provider, duration, prompt_tokens, completion_tokens, cache_hit=False)
            
            return result
            
        except Exception as exc:
            duration = time.time() - start_time
            logger.error(f"LLMManager: Task '{task_type}' failed after all fallbacks: {exc}")
            await cls._log_metrics(task_type, model, provider, duration, 0, 0, cache_hit=False, failed=True, error_msg=str(exc))
            raise exc

    @classmethod
    async def _execute_with_retry_and_fallback(
        cls,
        task_type: str,
        messages: List[Dict[str, str]],
        provider: str,
        model: str,
        fallback_provider: Optional[str],
        fallback_model: Optional[str],
        user_id: str,
        temperature: float,
        tools: Optional[List],
        tool_choice: Optional[str]
    ) -> Dict[str, Any]:
        """Try primary provider with retries, then fallback to alternative provider."""
        try:
            return await cls._execute_call(provider, model, messages, user_id, temperature, tools, tool_choice)
        except Exception as e:
            logger.warning(f"LLMManager: Primary provider '{provider}' failed for '{task_type}': {e}. Trying fallback...")
            if fallback_provider and fallback_model:
                try:
                    return await cls._execute_call(fallback_provider, fallback_model, messages, user_id, temperature, tools, tool_choice)
                except Exception as fe:
                    logger.error(f"LLMManager: Fallback provider '{fallback_provider}' also failed for '{task_type}': {fe}")
                    raise fe
            raise e

    @classmethod
    async def _execute_call(
        cls,
        provider: str,
        model: str,
        messages: List[Dict[str, str]],
        user_id: str,
        temperature: float,
        tools: Optional[List],
        tool_choice: Optional[str]
    ) -> Dict[str, Any]:
        """Perform the actual call under semaphore with retry backoff."""
        from app.config.groq_config import llm_chat_completion
        
        sem = cls._semaphores.get(provider, cls._semaphores["groq"])
        
        async with sem:
            max_retries = 3
            backoff = 1.0
            
            for attempt in range(max_retries):
                try:
                    # Execute synchronous/asynchronous LLM call cleanly
                    # Since llm_chat_completion runs synchronously in a thread/directly,
                    # we wrap it in a thread pool execution if needed or call directly.
                    loop = asyncio.get_event_loop()
                    
                    def _call():
                        return llm_chat_completion(
                            messages=messages,
                            model=model,
                            provider=provider,
                            tools=tools,
                            tool_choice=tool_choice,
                            temperature=temperature,
                            user_id=user_id
                        )
                        
                    chat_completion = await loop.run_in_executor(None, _call)
                    
                    response_message = chat_completion.choices[0].message
                    tool_calls = None
                    if response_message.tool_calls:
                        tool_calls = []
                        for tc in response_message.tool_calls:
                            tool_calls.append({
                                "id": tc.id,
                                "type": tc.type,
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments
                                }
                            })
                            
                    return {
                        "content": response_message.content or "",
                        "tool_calls": tool_calls,
                        "model": model,
                        "provider": provider
                    }
                    
                except Exception as e:
                    error_str = str(e).lower()
                    # Trigger retry on HTTP 429 or rate limits
                    is_rate_limit = "429" in error_str or "rate limit" in error_str or "too many requests" in error_str
                    if is_rate_limit and attempt < max_retries - 1:
                        sleep_time = backoff * (1.5 + random.random())
                        logger.warning(f"LLMManager: Rate limited on '{provider}' ({model}). Retrying in {sleep_time:.2f}s...")
                        await asyncio.sleep(sleep_time)
                        backoff *= 2
                    else:
                        raise e

    @classmethod
    async def _log_metrics(
        cls,
        task_type: str,
        model: str,
        provider: str,
        duration: float,
        prompt_tokens: int,
        completion_tokens: int,
        cache_hit: bool,
        failed: bool = False,
        error_msg: Optional[str] = None
    ) -> None:
        """Write execution metrics to MongoDB for analytics logging."""
        try:
            db = await get_database()
            metrics = {
                "task_type": task_type,
                "model": model,
                "provider": provider,
                "duration_seconds": duration,
                "prompt_tokens_est": prompt_tokens,
                "completion_tokens_est": completion_tokens,
                "cache_hit": cache_hit,
                "failed": failed,
                "error": error_msg,
                "timestamp": datetime.now(timezone.utc)
            }
            await db.app_metrics.insert_one(metrics)
        except Exception as e:
            logger.warning(f"LLMManager: Failed to log metrics to db: {e}")
