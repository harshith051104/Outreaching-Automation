import logging
import asyncio
import uuid
from orchestrator.state import ExecutionState
from orchestrator.context import ExecutionContext

logger = logging.getLogger("VerifyConcurrency")

async def run_workflow_instance(instance_id: int, delay: float, var_val: str):
    """Simulate a workflow running concurrently to check context variable isolation."""
    # 1. State
    state = ExecutionState(workflow_id=f"wf_instance_{instance_id}", workflow_version="1.0.0")
    
    # 2. Context
    context = ExecutionContext(
        campaign={"id": f"campaign_{instance_id}"},
        user={"id": f"user_{instance_id}"},
        variables={"my_isolated_key": var_val},
        correlation_id=state.workflow_run_id
    )
    
    # Simulate processing delay
    await asyncio.sleep(delay)
    
    # Check context is still holding the same input variable (no contamination)
    return {
        "workflow_run_id": state.workflow_run_id,
        "input_val": context.variables.get("my_isolated_key"),
        "campaign_id": context.campaign.get("id"),
        "user_id": context.user.get("id")
    }

async def run_test() -> bool:
    logger.info("[*] Running Concurrency & Context Isolation Verification...")
    
    # Run 5 workflow instances concurrently
    tasks = [
        run_workflow_instance(i, delay=0.05 * (5 - i), var_val=f"value_for_{i}")
        for i in range(1, 6)
    ]
    
    results = await asyncio.gather(*tasks)
    
    # Verifications
    run_ids = set()
    for idx, r in enumerate(results, 1):
        run_id = r["workflow_run_id"]
        val = r["input_val"]
        campaign_id = r["campaign_id"]
        user_id = r["user_id"]
        
        # Verify unique IDs
        if run_id in run_ids:
            logger.error(f"[-] Duplicate execution ID detected: {run_id}")
            return False
        run_ids.add(run_id)
        
        # Verify variable context isolation
        expected_val = f"value_for_{idx}"
        if val != expected_val:
            logger.error(f"[-] Context contamination: got variable '{val}', expected '{expected_val}'")
            return False
            
        # Verify campaign and user isolation
        if campaign_id != f"campaign_{idx}" or user_id != f"user_{idx}":
            logger.error(f"[-] Context metadata leak: campaign={campaign_id}, user={user_id}")
            return False
            
    logger.info(f"[+] Successfully verified context isolation across {len(results)} concurrent runs.")
    logger.info("[+] Concurrency & Context Verification: PASSED")
    return True
