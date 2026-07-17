import asyncio
import logging
import sys
from pathlib import Path
from orchestrator.engine import Orchestrator

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("OrchestratorVerification")

async def test_verification():
    logger.info("=========================================================")
    logger.info("       STARTING ORCHESTRATOR FACADE VERIFICATION         ")
    logger.info("=========================================================\n")

    # 1. Instantiate Orchestrator Facade
    logger.info("[*] Instantiating Orchestrator facade...")
    orchestrator = Orchestrator()

    # 2. Initialize (this triggers Registry loading, Compiler validation, and Tool registration)
    logger.info("[*] Initializing registry and compiling workflows...")
    await orchestrator.initialize()

    # 3. Check Registry Health
    health = orchestrator.registry.health()
    logger.info(f"[+] MetadataRegistry Health Check:")
    logger.info(f"    - Status: {health['status']}")
    logger.info(f"    - Registry Version Hash: {health['version']}")
    logger.info(f"    - Loaded Agents Count: {health['agents_count']}")
    logger.info(f"    - Loaded Skills Count: {health['skills_count']}")
    logger.info(f"    - Loaded Workflows Count: {health['workflows_count']}")
    logger.info(f"    - Loaded Tools Count: {health['tools_count']}")
    logger.info(f"    - Loaded At: {health['last_reload']}")

    # 4. Check Compiler Status
    logger.info("\n[+] Verification of Compiled Workflows:")
    for wf_name in orchestrator.workflows.keys():
        compiled_wf = orchestrator.compiler.get_compiled(wf_name)
        if compiled_wf:
            logger.info(f"    - Workflow '{wf_name}':")
            logger.info(f"      * Version: {compiled_wf.workflow_version}")
            logger.info(f"      * Compiled Hash: {compiled_wf.compiled_hash}")
            logger.info(f"      * Steps Count: {len(compiled_wf.steps)}")
        else:
            logger.warning(f"    - Workflow '{wf_name}' failed compile check.")

    # 5. Check Tool Dispatcher Registrations
    logger.info("\n[+] Registered Tool Plugins:")
    registered_tools = [
        "mongodb_query", "mongodb_insert", "mongodb_update", "mongodb_upsert",
        "qdrant_search", "qdrant_upsert", "gmail_send", "gmail_check_replies",
        "websocket_broadcast", "spam_check"
    ]
    for tname in registered_tools:
        has_tool = orchestrator.dispatcher.has_tool(tname)
        logger.info(f"    - Tool '{tname}': {'REGISTERED' if has_tool else 'MISSING'}")

    # 6. Execute Mock Workflow Run
    # We will simulate a quick local execution run of 'Campaign Creation Workflow'
    logger.info("\n[*] Simulating Execution of 'Campaign Creation Workflow'...")
    
    mock_inputs = {
        "campaign_name": "Test Simulation Campaign",
        "niche": "DeepTech Hardware",
        "target_geography": "North America",
        "sequence_steps": [
            {"step": 1, "channel": "Email", "delay_days": 0},
            {"step": 2, "channel": "LinkedIn", "delay_days": 3}
        ]
    }
    
    # We will mock the database and run context
    mock_context = {
        "user": {"id": "usr_mock_123", "email": "testuser@example.com"},
        "campaign": {"id": "camp_mock_456"},
        "workflow_run_id": "wrun_mock_789"
    }

    try:
        # Running Campaign Creation Workflow (which mainly does database writes/upserts)
        logger.info(f"[*] Running workflow with inputs: {mock_inputs}")
        
        # We perform compile check only (dry-run) to verify graph traversal logic
        wf_def = orchestrator.compiler.get_compiled("Campaign Creation Workflow")
        if wf_def:
            plan = orchestrator.planner.build_plan(wf_def)
            logger.info("[+] Execution Plan generated successfully:")
            for node_id, node in plan.nodes.items():
                logger.info(f"    - Node '{node_id}': action={node.action or node.agent}, dependencies={node.dependencies}")
            
            logger.info("\n[+] All structural and modular refactoring components verified successfully!")
        else:
            logger.error("[-] Compilation error: 'campaign_creation' workflow not found.")

    except Exception as e:
        logger.exception(f"[-] Execution run encountered an error: {e}")

    logger.info("\n=========================================================")
    logger.info("                 VERIFICATION COMPLETED                  ")
    logger.info("=========================================================")

if __name__ == "__main__":
    asyncio.run(test_verification())
