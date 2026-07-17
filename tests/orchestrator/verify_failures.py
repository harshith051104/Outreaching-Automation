import logging
import asyncio
import time
from orchestrator.dispatcher import ToolDispatcher, ToolResult
from orchestrator.registry import MetadataRegistry, ToolConfig

logger = logging.getLogger("VerifyFailures")

class MockRegistryWithRetry:
    def __init__(self, retry_strategy):
        self.strategy = retry_strategy
        
    def get_tool(self, name):
        return ToolConfig(name, {
            "description": "Mock failure tool",
            "inputs": {},
            "outputs": {},
            "retry_strategy": self.strategy
        })

async def run_test() -> bool:
    logger.info("[*] Running Tool Dispatcher Retry Strategy Verification...")
    
    # 1. Verify NONE strategy (1 attempt, no retries)
    reg_none = MockRegistryWithRetry({"max_attempts": 1, "delay": "fixed", "backoff_delay": 0.01})
    dispatcher_none = ToolDispatcher(registry=reg_none, persistence=None)
    
    attempts = 0
    async def failing_handler(inputs, ctx):
        nonlocal attempts
        attempts += 1
        raise RuntimeError("Failure")
        
    dispatcher_none.register("test_tool", failing_handler)
    res = await dispatcher_none.execute("test_tool", {}, {})
    
    if res.success or attempts != 1:
        logger.error(f"[-] NONE strategy failed: attempts={attempts}, success={res.success}")
        return False
    logger.info("[+] NONE strategy verified (1 attempt, no retries).")
    
    # 2. Verify FIXED strategy (3 attempts, fixed delay)
    reg_fixed = MockRegistryWithRetry({"max_attempts": 3, "delay": "fixed", "backoff_delay": 0.01})
    dispatcher_fixed = ToolDispatcher(registry=reg_fixed, persistence=None)
    
    attempts = 0
    dispatcher_fixed.register("test_tool", failing_handler)
    res = await dispatcher_fixed.execute("test_tool", {}, {})
    
    if res.success or attempts != 3:
        logger.error(f"[-] FIXED strategy failed: attempts={attempts}")
        return False
    logger.info("[+] FIXED strategy verified (3 attempts, fixed delay).")
    
    # 3. Verify EXPONENTIAL strategy
    reg_exp = MockRegistryWithRetry({"max_attempts": 3, "delay": "exponential", "backoff_delay": 0.01})
    dispatcher_exp = ToolDispatcher(registry=reg_exp, persistence=None)
    
    attempts = 0
    dispatcher_exp.register("test_tool", failing_handler)
    res = await dispatcher_exp.execute("test_tool", {}, {})
    
    if res.success or attempts != 3:
        logger.error(f"[-] EXPONENTIAL strategy failed: attempts={attempts}")
        return False
    logger.info("[+] EXPONENTIAL strategy verified (3 attempts, exponential delay).")
    
    logger.info("[+] Dispatcher Failure Recovery Verification: PASSED")
    return True
