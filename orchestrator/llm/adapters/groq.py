import logging
from typing import Dict, Any, List
from orchestrator.llm.adapters.base import BaseLLMAdapter
from app.config.settings import settings

logger = logging.getLogger(__name__)

class GroqAdapter(BaseLLMAdapter):
    """Adapter for Groq LLM API integrations."""
    async def generate(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        user_id: str
    ) -> Dict[str, Any]:
        # Route to Groq using our LLMManager sync or async calls
        # We can implement a clean direct call here or reuse LLMManager execution helper
        from groq import AsyncGroq
        try:
            client = AsyncGroq(api_key=settings.GROQ_API_KEY)
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return {
                "content": response.choices[0].message.content,
                "model": model,
                "provider": "groq",
                "usage": {
                    "prompt_tokens": getattr(response.usage, "prompt_tokens", 0),
                    "completion_tokens": getattr(response.usage, "completion_tokens", 0)
                }
            }
        except Exception as e:
            logger.error(f"GroqAdapter: Request failed: {e}")
            raise e
