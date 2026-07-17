import logging
import time
from typing import Dict, Any, Optional, List
from app.config.mongodb_config import get_database

logger = logging.getLogger(__name__)

class PersistenceService:
    """Handles async MongoDB persistence for engine execution logs, artifacts, runs, and metrics."""
    
    @classmethod
    async def save_workflow_run(cls, run_id: str, state_dict: Dict[str, Any]) -> None:
        try:
            db = await get_database()
            state_dict["updated_at"] = time.time()
            await db.workflow_runs.update_one(
                {"workflow_run_id": run_id},
                {"$set": state_dict},
                upsert=True
            )
        except Exception as e:
            logger.warning(f"PersistenceService: Failed to save workflow run {run_id}: {e}")

    @classmethod
    async def get_workflow_run(cls, run_id: str) -> Optional[Dict[str, Any]]:
        try:
            db = await get_database()
            return await db.workflow_runs.find_one({"workflow_run_id": run_id})
        except Exception as e:
            logger.warning(f"PersistenceService: Failed to retrieve workflow run {run_id}: {e}")
            return None

    @classmethod
    async def save_tool_run(
        cls,
        tool_run_id: str,
        workflow_run_id: str,
        tool_name: str,
        inputs: Dict[str, Any],
        result: Dict[str, Any],
        duration: float,
        retry_count: int = 0,
        error: Optional[str] = None
    ) -> None:
        try:
            db = await get_database()
            doc = {
                "tool_run_id": tool_run_id,
                "workflow_run_id": workflow_run_id,
                "tool_name": tool_name,
                "inputs": inputs,
                "result": result,
                "duration": duration,
                "retry_count": retry_count,
                "error": error,
                "timestamp": time.time()
            }
            await db.tool_runs.insert_one(doc)
        except Exception as e:
            logger.warning(f"PersistenceService: Failed to save tool run {tool_run_id}: {e}")

    @classmethod
    async def save_llm_call(
        cls,
        llm_call_id: str,
        workflow_run_id: str,
        provider: str,
        model: str,
        messages: List[Dict[str, str]],
        response: Dict[str, Any],
        duration: float,
        prompt_tokens: int,
        completion_tokens: int,
        error: Optional[str] = None
    ) -> None:
        try:
            db = await get_database()
            doc = {
                "llm_call_id": llm_call_id,
                "workflow_run_id": workflow_run_id,
                "provider": provider,
                "model": model,
                "messages": messages,
                "response": response,
                "duration": duration,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "error": error,
                "timestamp": time.time()
            }
            await db.llm_calls.insert_one(doc)
        except Exception as e:
            logger.warning(f"PersistenceService: Failed to save LLM call {llm_call_id}: {e}")

    @classmethod
    async def save_artifact(
        cls,
        artifact_id: str,
        workflow_run_id: str,
        step_id: str,
        payload: Any,
        metadata: Dict[str, Any]
    ) -> None:
        try:
            db = await get_database()
            doc = {
                "artifact_id": artifact_id,
                "workflow_run_id": workflow_run_id,
                "step_id": step_id,
                "payload": payload,
                "metadata": metadata,
                "timestamp": time.time()
            }
            await db.artifacts.insert_one(doc)
        except Exception as e:
            logger.warning(f"PersistenceService: Failed to save artifact {artifact_id}: {e}")

    @classmethod
    async def save_execution_log(
        cls,
        workflow_run_id: str,
        message: str,
        level: str = "INFO",
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        try:
            db = await get_database()
            doc = {
                "workflow_run_id": workflow_run_id,
                "message": message,
                "level": level,
                "metadata": metadata or {},
                "timestamp": time.time()
            }
            await db.execution_logs.insert_one(doc)
        except Exception as e:
            logger.warning(f"PersistenceService: Failed to save execution log: {e}")
