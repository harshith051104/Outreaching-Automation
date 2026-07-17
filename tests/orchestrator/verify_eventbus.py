import asyncio
import logging
from orchestrator.event_bus import EventBus

logger = logging.getLogger("VerifyEventBus")

async def run_test() -> bool:
    logger.info("[*] Running EventBus Sequence Order Verification...")
    
    bus = EventBus()
    event_sequence = []
    
    # Subscribe to catch all events in order
    async def log_event(topic, data):
        event_sequence.append(topic)
        
    bus.subscribe("*", log_event)
    
    # Publish events in the chronological execution sequence
    await bus.publish("workflow.started", {"id": "wf_1"})
    await bus.publish("step.started", {"step": "step_1"})
    await bus.publish("tool.started", {"tool": "mongodb_insert"})
    await bus.publish("tool.finished", {"tool": "mongodb_insert", "success": True})
    await bus.publish("step.completed", {"step": "step_1"})
    await bus.publish("workflow.completed", {"id": "wf_1"})
    
    # Wait for async loop dispatch
    await asyncio.sleep(0.1)
    
    expected_order = [
        "workflow.started",
        "step.started",
        "tool.started",
        "tool.finished",
        "step.completed",
        "workflow.completed"
    ]
    
    logger.info(f"[+] Received event sequence: {event_sequence}")
    
    if event_sequence != expected_order:
        logger.error(f"[-] Invalid event sequence order. Got {event_sequence}, expected {expected_order}")
        return False
        
    logger.info("[+] EventBus sequence order verified successfully!")
    logger.info("[+] EventBus Verification: PASSED")
    return True
