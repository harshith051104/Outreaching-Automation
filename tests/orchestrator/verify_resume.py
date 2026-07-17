import logging
from orchestrator.state import ExecutionState

logger = logging.getLogger("VerifyResume")

async def run_test() -> bool:
    logger.info("[*] Running Checkpoint Recovery & Resume Verification...")
    
    # 1. Simulate workflow run up to step_2
    state = ExecutionState(workflow_id="campaign_execution", workflow_version="1.0.0")
    state.completed_nodes = ["step_1"]
    state.current_node = "step_2"
    state.variables = {"my_state_val": "persisted_value"}
    state.artifacts = [{"artifact_id": "art_1", "step_id": "step_1", "payload": {"out": "step_1_res"}}]
    
    # Serialize to dictionary (checkpoint snapshot saved to database)
    snapshot = state.to_dict()
    
    # 2. Deserialize to construct a resume run state
    resumed_state = ExecutionState.from_dict(snapshot)
    
    # Verifications
    if resumed_state.workflow_id != "campaign_execution":
        logger.error(f"[-] Invalid workflow ID: {resumed_state.workflow_id}")
        return False
        
    if "step_1" not in resumed_state.completed_nodes:
        logger.error(f"[-] Missing completed nodes in snapshot: {resumed_state.completed_nodes}")
        return False
        
    if resumed_state.current_node != "step_2":
        logger.error(f"[-] Incorrect current node resumed: {resumed_state.current_node}")
        return False
        
    if resumed_state.variables.get("my_state_val") != "persisted_value":
        logger.error(f"[-] Incorrect variables state resumed: {resumed_state.variables}")
        return False
        
    if len(resumed_state.artifacts) != 1 or resumed_state.artifacts[0]["artifact_id"] != "art_1":
        logger.error(f"[-] Checkpoint artifacts missing: {resumed_state.artifacts}")
        return False
        
    logger.info("[+] Checkpoint snapshot verification passed successfully.")
    logger.info("[+] Checkpoint Resume Verification: PASSED")
    return True
