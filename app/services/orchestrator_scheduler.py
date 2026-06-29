"""
Orchestration Execution Scheduler.

Parses execution plans, resolves dependencies, and schedules worker tasks in order
(sequential dependencies first, followed by concurrent execution of independent tasks).
"""

import asyncio
import logging
from typing import Any, Dict, List, Set, Optional, Tuple

from app.services.orchestrator_worker import (
    CampaignWorker,
    LeadWorker,
    SheetsWorker,
    NotificationWorker,
    TimelineWorker,
    BatchContentWorker
)

logger = logging.getLogger(__name__)

# Map tool names to worker methods
WORKER_MAP = {
    "create_campaign": CampaignWorker.create_campaign,
    "start_campaign": CampaignWorker.start_campaign,
    "pause_campaign": CampaignWorker.pause_campaign,
    "update_campaign": CampaignWorker.update_campaign,
    "import_leads": LeadWorker.import_leads,
    "generate_batch_content": BatchContentWorker.generate_batch_content,
    "sync_google_sheet": SheetsWorker.sync_google_sheet,
    "notify_team": NotificationWorker.notify_team,
    "log_timeline": TimelineWorker.log_timeline
}


class OrchestratorScheduler:
    """Dependency-aware task scheduler for the Orchestration Engine."""

    @classmethod
    async def execute_plan(
        cls,
        user_id: str,
        plan: Dict[str, Any],
        initial_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Parse and execute the structured plan while enforcing step dependencies.
        """
        logger.info(f"OrchestratorScheduler: Beginning execution of plan for user {user_id}")
        
        context = initial_context or {}
        execution_list = plan.get("execution", [])
        
        if not execution_list:
            logger.warning("OrchestratorScheduler: Plan execution list is empty.")
            return {"status": "success", "actions_taken": [], "results": {}}

        # Store general campaign info from the plan header into the shared context
        if "campaign" in plan and isinstance(plan["campaign"], dict):
            for k, v in plan["campaign"].items():
                context[k] = v

        completed_tasks: Set[str] = set()
        task_results: Dict[str, Any] = {}
        actions_taken: List[Dict[str, Any]] = []

        # 1. Identify dependencies and organize tasks
        # Separate tasks into:
        # - Sequential Tasks: has dependencies, or is a dependency of another task.
        # - Parallel Tasks: has parallel=True or has no dependencies/dependents.
        sequential_tasks: List[Dict[str, Any]] = []
        parallel_tasks: List[Dict[str, Any]] = []

        # Find which tasks are dependencies for other tasks
        all_dependencies: Set[str] = set()
        for task in execution_list:
            deps = task.get("depends_on", [])
            for dep in deps:
                all_dependencies.add(dep)

        for task in execution_list:
            tool_name = task.get("tool")
            task_id = task.get("id") or tool_name
            task["id"] = task_id  # ensure task has ID
            
            is_parallel = task.get("parallel", False)
            has_deps = len(task.get("depends_on", [])) > 0
            is_dependency_of_others = task_id in all_dependencies
            
            if is_parallel and not has_deps and not is_dependency_of_others:
                parallel_tasks.append(task)
            else:
                sequential_tasks.append(task)

        # 2. Execute Sequential / Dependent Tasks in order of resolution
        # We perform a simple topological resolution loop
        remaining_seq = list(sequential_tasks)
        
        while remaining_seq:
            # Find tasks with all dependencies met
            ready_tasks = [
                t for t in remaining_seq 
                if all(dep in completed_tasks for dep in t.get("depends_on", []))
            ]
            
            if not ready_tasks:
                # Cycle detected or unresolved dependency
                unresolved = [t.get("id") for t in remaining_seq]
                logger.error(f"OrchestratorScheduler: Unresolved dependencies or cycle detected in tasks: {unresolved}")
                break
                
            for task in ready_tasks:
                task_id = task["id"]
                tool_name = task.get("tool")
                
                # Execute the worker
                result = await cls._run_worker(tool_name, task.get("arguments", {}), user_id, context)
                task_results[task_id] = result
                actions_taken.append({"tool": tool_name, "id": task_id, "status": result.get("status")})
                
                if result.get("status") == "success":
                    completed_tasks.add(task_id)
                    # Merge worker output into shared context for downstream tasks
                    for key in ["campaign", "leads", "subject_template", "body_template", "sequence_steps"]:
                        if key in result:
                            context[key] = result[key]
                            if key == "campaign" and isinstance(result[key], dict) and "id" in result[key]:
                                context["campaign_id"] = result[key]["id"]
                else:
                    # Critical task failed: abort dependent steps
                    error_msg = result.get("error", "Unknown error")
                    logger.error(f"OrchestratorScheduler: Critical task '{task_id}' failed: {error_msg}. Aborting dependent runs.")
                    return {
                        "status": "failed",
                        "error": f"Critical task '{task_id}' failed: {error_msg}",
                        "actions_taken": actions_taken,
                        "results": task_results
                    }
                    
                remaining_seq.remove(task)

        # 3. Execute Independent Parallel Tasks
        if parallel_tasks:
            logger.info(f"OrchestratorScheduler: Executing {len(parallel_tasks)} tasks in parallel...")
            
            async def _run_parallel_wrapper(task: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
                tool_name = task.get("tool")
                task_id = task["id"]
                try:
                    res = await cls._run_worker(tool_name, task.get("arguments", {}), user_id, context)
                    return task_id, res
                except Exception as e:
                    logger.warning(f"OrchestratorScheduler: Parallel task '{task_id}' threw exception: {e}")
                    return task_id, {"status": "failed", "error": str(e)}

            tasks = [asyncio.create_task(_run_parallel_wrapper(t)) for t in parallel_tasks]
            parallel_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for res_val in parallel_results:
                if isinstance(res_val, tuple):
                    task_id, res = res_val
                    # Log but do not fail the overall campaign if a parallel task fails
                    task_results[task_id] = res
                    # Find tool name associated with this task ID
                    t_name = next((t.get("tool") for t in parallel_tasks if t["id"] == task_id), "unknown")
                    actions_taken.append({"tool": t_name, "id": task_id, "status": res.get("status")})
                    
                    if res.get("status") != "success":
                        logger.warning(f"OrchestratorScheduler: Non-critical parallel task '{task_id}' failed: {res.get('error')}")

        logger.info("OrchestratorScheduler: Plan execution complete.")
        return {
            "status": "success",
            "actions_taken": actions_taken,
            "results": task_results,
            "context": context
        }

    @classmethod
    async def _run_worker(cls, tool_name: str, args: Dict[str, Any], user_id: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve and run a worker by name, falling back to execute_tool for other tools."""
        worker_func = WORKER_MAP.get(tool_name)
        if worker_func:
            try:
                return await worker_func(user_id=user_id, args=args, context=context)
            except Exception as e:
                logger.exception(f"OrchestratorScheduler: Worker execution exception on '{tool_name}'")
                return {"status": "failed", "error": str(e)}
        else:
            logger.info(f"OrchestratorScheduler: Falling back to legacy execute_tool for '{tool_name}'")
            from app.services.chatbot_service import execute_tool
            try:
                out_str = await execute_tool(
                    name=tool_name,
                    args=args,
                    user_id=user_id,
                    uploaded_files=context.get("uploaded_files"),
                    chat_session_id=context.get("chat_session_id")
                )
                try:
                    res_data = json.loads(out_str)
                    if isinstance(res_data, dict):
                        if "status" not in res_data:
                            res_data["status"] = "success"
                        return res_data
                except:
                    pass
                return {"status": "success", "raw_output": out_str}
            except Exception as e:
                logger.exception(f"OrchestratorScheduler: Legacy execute_tool failed on '{tool_name}'")
                return {"status": "failed", "error": str(e)}
