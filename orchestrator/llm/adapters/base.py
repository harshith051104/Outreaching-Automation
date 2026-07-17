from typing import Dict, Any, List

class BaseLLMAdapter:
    """Base interface for all LLM provider adapters."""
    async def generate(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        user_id: str
    ) -> Dict[str, Any]:
        raise NotImplementedError
