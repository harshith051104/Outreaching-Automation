import logging
from orchestrator.persistence import PersistenceService

logger = logging.getLogger("VerifyPersistence")

class MockDB:
    def __init__(self):
        self.workflow_runs = []
        self.tool_runs = []
        self.llm_calls = []
        self.artifacts = []
        
    async def insert_one(self, collection_name, doc):
        if collection_name == "workflow_runs":
            self.workflow_runs.append(doc)
        elif collection_name == "tool_runs":
            self.tool_runs.append(doc)
        elif collection_name == "llm_calls":
            self.llm_calls.append(doc)
        elif collection_name == "artifacts":
            self.artifacts.append(doc)

class CustomMockDB:
    def __init__(self, mock_db):
        self.mock_db = mock_db
        
    def __getattr__(self, name):
        class Coll:
            def __init__(self, mock_db, name):
                self.mock_db = mock_db
                self.name = name
            async def insert_one(self, doc):
                await self.mock_db.insert_one(self.name, doc)
            async def update_one(self, query, update, upsert=False):
                doc = update.get("$set", {})
                await self.mock_db.insert_one(self.name, doc)
        return Coll(self.mock_db, name)

async def run_test() -> bool:
    logger.info("[*] Running Persistence Consistency Verification...")
    
    mock_db = MockDB()
    persistence = PersistenceService()
    
    import orchestrator.persistence as p_mod
    original_get_db = p_mod.get_database
    
    async def mock_get_db():
        return CustomMockDB(mock_db)
        
    p_mod.get_database = mock_get_db
    
    execution_id = "exec_id_consistency_check_123"
    
    try:
        # Save a workflow run
        await persistence.save_workflow_run(execution_id, {"workflow_id": "test_wf", "status": "COMPLETED"})
        
        # Save a tool run
        await persistence.save_tool_run(
            tool_run_id="trun_1",
            workflow_run_id=execution_id,
            tool_name="test_tool",
            inputs={},
            result={},
            duration=0.1,
            retry_count=0
        )
        
        # Save an LLM call
        await persistence.save_llm_call(
            llm_call_id="llm_1",
            workflow_run_id=execution_id,
            provider="groq",
            model="llama-3",
            messages=[],
            response={},
            duration=0.5,
            prompt_tokens=10,
            completion_tokens=20
        )
        
        # Save an artifact
        await persistence.save_artifact(
            artifact_id="art_1",
            workflow_run_id=execution_id,
            step_id="step_1",
            payload={"output": "test"},
            metadata={"execution_id": execution_id}
        )
        
        # 2. Assert consistency of execution ID across collections
        if not mock_db.workflow_runs:
            logger.error("[-] Workflow run was not saved")
            return False
            
        # Verify tool runs execution ID
        tr_exec_id = mock_db.tool_runs[0].get("workflow_run_id")
        if tr_exec_id != execution_id:
            logger.error(f"[-] Tool run has incorrect execution ID: {tr_exec_id}")
            return False
            
        # Verify LLM calls execution ID
        llm_exec_id = mock_db.llm_calls[0].get("workflow_run_id")
        if llm_exec_id != execution_id:
            logger.error(f"[-] LLM call has incorrect execution ID: {llm_exec_id}")
            return False
            
        # Verify artifacts execution ID
        art_exec_id = mock_db.artifacts[0].get("workflow_run_id")
        if art_exec_id != execution_id:
            logger.error(f"[-] Artifact has incorrect execution ID: {art_exec_id}")
            return False
            
        logger.info("[+] Persistence Consistency: All written documents share the same execution ID.")
        
    finally:
        # Restore original database function
        p_mod.get_database = original_get_db
        
    logger.info("[+] Persistence Consistency Verification: PASSED")
    return True
