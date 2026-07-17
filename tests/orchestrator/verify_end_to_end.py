import logging
from orchestrator.engine import Orchestrator

logger = logging.getLogger("VerifyEndToEnd")

class MockLLM:
    async def generate_completion(self, *args, **kwargs):
        return {"provider": "groq", "model": "llama-3.3", "content": '{"valid": true}'}

async def run_test() -> bool:
    logger.info("[*] Running End-to-End Workflow Execution Verification...")
    
    # 1. Instantiate orchestrator
    orchestrator = Orchestrator()
    # Temporarily set validation level to WARN so legacy YAML files compile on initialize
    orchestrator.compiler.validation_level = "WARN"
    await orchestrator.initialize()
    
    # 2. Inject mock LLM to avoid remote rate limits during verification
    orchestrator.llm_interface = MockLLM()
    orchestrator.workflow_executor.skill_runtime.llm_interface = MockLLM()
    
    # 3. Register mock tool handlers for campaign creation steps
    async def mock_handler(inputs, ctx):
        return {"status": "success", "id": "mock_id_123", "data": inputs}
        
    mock_tools = ["resolve_or_select_gmail", "build_campaign_document", "mongodb_insert", "create_default_steps"]
    for tname in mock_tools:
        if tname in orchestrator.dispatcher._handlers:
            del orchestrator.dispatcher._handlers[tname]
        orchestrator.dispatcher.register(tname, mock_handler)
    
    mock_inputs = {
        "campaign_name": "DeepTech hardware campaign",
        "niche": "DeepTech Hardware",
        "target_geography": "North America",
        "sequence_steps": [
            {"step": 1, "channel": "Email", "delay_days": 0}
        ]
    }
    
    # 4. Execute Campaign Creation Workflow end-to-end
    try:
        res = await orchestrator.execute_workflow(
            workflow_name="Campaign Creation Workflow",
            inputs=mock_inputs,
            context={
                "user": {"id": "usr_mock_123", "email": "testuser@example.com"},
                "campaign": {"id": "camp_mock_456"},
                "workflow_run_id": "wrun_mock_789"
            }
        )
        logger.info(f"[+] End-to-End execution finished. Result outputs: {res}")
        logger.info("[+] End-to-End Verification: PASSED")
        return True
    except Exception as e:
        logger.exception(f"[-] End-to-End execution failed: {e}")
        return False
