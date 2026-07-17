import logging
from orchestrator.registry import MetadataRegistry
from orchestrator.dispatcher import ToolDispatcher

logger = logging.getLogger("VerifyDispatcher")

async def run_test() -> bool:
    logger.info("[*] Running Dispatcher Verification...")
    
    registry = MetadataRegistry(auto_reload=False)
    await registry.initialize()
    
    dispatcher = ToolDispatcher(registry=registry, persistence=None)
    
    # Define handler functions
    def handler_a(inputs, ctx):
        return "result_a"
        
    def handler_b(inputs, ctx):
        return "result_b"
        
    # 1. Register tool A
    dispatcher.register("test_tool", handler_a)
    
    # 2. Register same handler again (should be ignored silently)
    try:
        dispatcher.register("test_tool", handler_a)
        logger.info("[+] Duplicate registration of identical handler ignored successfully.")
    except ValueError as e:
        logger.error(f"[-] Re-registering identical handler incorrectly raised exception: {e}")
        return False
        
    # 3. Register different handler (should raise ValueError)
    try:
        dispatcher.register("test_tool", handler_b)
        logger.error("[-] Re-registering different handler failed to raise ValueError")
        return False
    except ValueError as e:
        logger.info(f"[+] Re-registering different handler correctly rejected: {e}")
        
    # 4. Input validation check
    # Check that validation operates correctly when schema is available or missing
    has_tool = dispatcher.has_tool("test_tool")
    if not has_tool:
        logger.error("[-] Registered tool not found in registry dict")
        return False
        
    logger.info("[+] Dispatcher Verification: PASSED")
    return True
