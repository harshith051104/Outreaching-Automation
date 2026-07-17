import logging
from orchestrator.state import ExecutionState

logger = logging.getLogger("VerifyRuntime")

async def run_test() -> bool:
    logger.info("[*] Running Runtime State Transition Verification...")
    
    # Initialize State
    state = ExecutionState(workflow_id="test_state_workflow", workflow_version="1.0.0")
    
    # 1. Verify CREATED state
    if state.status != "CREATED":
        logger.error(f"[-] Initial state is '{state.status}', expected 'CREATED'")
        return False
        
    # 2. Update status and transitions
    transitions = ["READY", "RUNNING", "WAITING", "COMPLETED"]
    for t in transitions:
        state.update_status(t)
        if state.status != t:
            logger.error(f"[-] State update failed: got '{state.status}', expected '{t}'")
            return False
            
    logger.info("[+] Linear state transitions verified successfully.")
    
    # 3. Verify Error and Paused states
    error_transitions = ["FAILED", "PAUSED", "CANCELLED"]
    for et in error_transitions:
        state.update_status(et)
        if state.status != et:
            logger.error(f"[-] Error/Control state update failed: got '{state.status}', expected '{et}'")
            return False
            
    logger.info("[+] Error, paused, and cancelled state transitions verified successfully.")
    logger.info("[+] Runtime State Verification: PASSED")
    return True
