import logging
from pathlib import Path
from orchestrator.registry import MetadataRegistry, WorkflowConfig
from orchestrator.compiler import WorkflowCompiler

logger = logging.getLogger("VerifyCompiler")

async def run_test() -> bool:
    logger.info("[*] Running Compiler Verification...")
    
    registry = MetadataRegistry(auto_reload=False)
    await registry.initialize()
    
    # 1. Test STRICT validation level (raising ValueError on unknown action)
    compiler_strict = WorkflowCompiler(validation_level="STRICT")
    
    wf_invalid = WorkflowConfig("invalid_action_test", Path("test.yaml"), {
        "version": "1.0.0",
        "steps": [
            {
                "id": "step_1",
                "action": "unknown_action_name_xyz",
                "input": {}
            }
        ],
        "outputs": {}
    })
    
    try:
        compiler_strict.compile(wf_invalid, registry)
        logger.error("[-] Strict mode failed: compiled workflow with missing action without error")
        return False
    except ValueError as e:
        logger.info(f"[+] Strict mode correctly rejected missing action: {e}")
        
    # 2. Test WARN validation level (should compile with warning)
    compiler_warn = WorkflowCompiler(validation_level="WARN")
    try:
        compiled = compiler_warn.compile(wf_invalid, registry)
        logger.info(f"[+] Warn mode successfully compiled invalid workflow. Hash: {compiled.compiled_hash}")
    except Exception as e:
        logger.error(f"[-] Warn mode incorrectly failed: {e}")
        return False
        
    # 3. Test circular dependency detection
    wf_circular = WorkflowConfig("circular_test", Path("test.yaml"), {
        "version": "1.0.0",
        "steps": [
            {
                "id": "step_1",
                "action": "pass_through",
                "input": {"data": "{{steps.step_2.output}}"}
            },
            {
                "id": "step_2",
                "action": "pass_through",
                "input": {"data": "{{steps.step_1.output}}"}
            }
        ],
        "outputs": {}
    })
    
    try:
        compiler_strict.compile(wf_circular, registry)
        logger.error("[-] Compiler failed to detect circular dependency")
        return False
    except ValueError as e:
        logger.info(f"[+] Compiler correctly detected cycle: {e}")
        
    logger.info("[+] Compiler Verification: PASSED")
    return True
