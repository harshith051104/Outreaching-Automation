import logging
import asyncio
from typing import Dict, Any, List
from orchestrator.llm.router import ProviderRouter
from orchestrator.llm.adapters.base import BaseLLMAdapter

logger = logging.getLogger("VerifyLLMRouter")

class MockAdapter(BaseLLMAdapter):
    def __init__(self, provider_name: str, behavior: str):
        self.provider_name = provider_name
        self.behavior = behavior # "success", "429", "offline"
        self.calls = 0
        
    async def generate(self, model: str, messages: List[Dict[str, str]], temperature: float, max_tokens: int, user_id: str) -> Dict[str, Any]:
        self.calls += 1
        if self.behavior == "429":
            raise RuntimeError("429 Too Many Requests: Rate limit exceeded")
        elif self.behavior == "offline":
            raise ConnectionError("Host unreachable: Connection timed out")
        return {
            "content": f"Response from {self.provider_name}",
            "provider": self.provider_name,
            "model": model
        }

async def run_test() -> bool:
    logger.info("[*] Running LLM Router Fallback Sequence Verification...")
    
    # Test case 1: Gemini (429) -> Gemma (Success)
    gemini_mock = MockAdapter("gemini", "429")
    gemma_mock = MockAdapter("gemma", "success")
    groq_mock = MockAdapter("groq", "success")
    
    router1 = ProviderRouter()
    router1._adapters = {
        "gemini": gemini_mock,
        "gemma": gemma_mock,
        "groq": groq_mock
    }
    
    # Set config mapping where primary is gemini and fallback is gemma
    import orchestrator.llm.router as router_mod
    router_mod.TASK_ROUTING_CONFIG["MOCK_TASK_1"] = {
        "provider": "gemini",
        "model": "gemini-1.5-pro",
        "fallback_provider": "gemma",
        "fallback_model": "gemma-4-26b"
    }
    
    res1 = await router1.route_and_generate(
        task_type="MOCK_TASK_1",
        messages=[{"role": "user", "content": "hello"}],
        user_id="user_123",
        retry_strategy="PROVIDER_FALLBACK",
        max_attempts=3,
        backoff_delay=0.01  # Keep it extremely fast
    )
    
    # Primary (gemini) is retried 3 times, then switches to fallback (gemma)
    if res1.get("provider") != "gemma" or gemini_mock.calls != 3 or gemma_mock.calls != 1:
        logger.error(f"[-] Gemini(429) -> Gemma fallback failed: {res1}, gemini={gemini_mock.calls}, gemma={gemma_mock.calls}")
        return False
    logger.info("[+] Fallback sequence: Gemini -> 429 -> Gemma -> Success verified.")
    
    # Test case 2: Gemma (Offline) -> Groq (Success)
    gemma_mock_offline = MockAdapter("gemma", "offline")
    router2 = ProviderRouter()
    router2._adapters = {
        "gemini": gemini_mock,
        "gemma": gemma_mock_offline,
        "groq": groq_mock
    }
    
    router_mod.TASK_ROUTING_CONFIG["MOCK_TASK_2"] = {
        "provider": "gemma",
        "model": "gemma-4-26b",
        "fallback_provider": "groq",
        "fallback_model": "llama-3.3-70b"
    }
    
    res2 = await router2.route_and_generate(
        task_type="MOCK_TASK_2",
        messages=[{"role": "user", "content": "hello"}],
        user_id="user_123",
        retry_strategy="PROVIDER_FALLBACK",
        max_attempts=3,
        backoff_delay=0.01
    )
    
    if res2.get("provider") != "groq" or gemma_mock_offline.calls != 3 or groq_mock.calls != 1:
        logger.error(f"[-] Gemma(offline) -> Groq fallback failed: {res2}")
        return False
        
    logger.info("[+] Fallback sequence: Gemma -> Offline -> Groq -> Success verified.")
    logger.info("[+] LLM Router Verification: PASSED")
    return True
