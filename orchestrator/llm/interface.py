import logging
import time
import uuid
from typing import Dict, Any, List, Optional
from orchestrator.llm.router import ProviderRouter

logger = logging.getLogger(__name__)

class LLMInterface:
    """Unified, provider-independent interface for LLM completions with persistence logging and metrics collection."""
    def __init__(self, persistence: Any, event_bus: Optional[Any] = None):
        self.persistence = persistence
        self.event_bus = event_bus
        self.router = ProviderRouter()

    async def generate_completion(
        self,
        task_type: str,
        messages: List[Dict[str, str]],
        user_id: str,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        retry_strategy: str = "EXPONENTIAL_JITTER",
        max_attempts: int = 3,
        backoff_delay: float = 1.0,
        workflow_run_id: str = "local"
    ) -> Dict[str, Any]:
        llm_call_id = f"llm_{uuid.uuid4()}"
        start_time = time.time()
        
        response = None
        error_msg = None
        
        try:
            response = await self.router.route_and_generate(
                task_type=task_type,
                messages=messages,
                user_id=user_id,
                temperature=temperature,
                max_tokens=max_tokens,
                retry_strategy=retry_strategy,
                max_attempts=max_attempts,
                backoff_delay=backoff_delay
            )
            return response
        except Exception as e:
            error_msg = str(e)
            raise e
        finally:
            duration = time.time() - start_time
            prompt_tokens = sum(len(m.get("content", "")) for m in messages) // 4
            completion_tokens = len(response.get("content", "")) // 4 if response else 0
            
            # Persist to database via PersistenceService
            if self.persistence:
                await self.persistence.save_llm_call(
                    llm_call_id=llm_call_id,
                    workflow_run_id=workflow_run_id,
                    provider=response.get("provider", "unknown") if response else "unknown",
                    model=response.get("model", "unknown") if response else "unknown",
                    messages=messages,
                    response=response or {},
                    duration=duration,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    error=error_msg
                )

            # Publish event
            if self.event_bus:
                await self.event_bus.publish(
                    topic="llm.call",
                    event_data={
                        "llm_call_id": llm_call_id,
                        "workflow_run_id": workflow_run_id,
                        "duration": duration,
                        "success": response is not None,
                        "error": error_msg
                    }
                )
