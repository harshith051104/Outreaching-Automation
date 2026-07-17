import logging
from typing import Dict, Any, List
from orchestrator.llm.adapters.base import BaseLLMAdapter
from app.config.groq_config import llm_chat_completion

logger = logging.getLogger(__name__)

class GeminiAdapter(BaseLLMAdapter):
    """Adapter for Google Gemini LLM API integrations."""
    async def generate(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        user_id: str
    ) -> Dict[str, Any]:
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            
            def _call():
                return llm_chat_completion(
                    messages=messages,
                    model=model,
                    provider="gemini",
                    temperature=temperature,
                    max_tokens=max_tokens,
                    user_id=user_id
                )
                
            response = await loop.run_in_executor(None, _call)
            return {
                "content": response.choices[0].message.content or "",
                "model": model,
                "provider": "gemini",
                "usage": {
                    "prompt_tokens": 0,
                    "completion_tokens": 0
                }
            }
        except Exception as e:
            logger.error(f"GeminiAdapter: Request failed: {e}")
            raise e
