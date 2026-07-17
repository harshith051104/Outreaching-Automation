import asyncio
import logging
import shutil
from pathlib import Path
from orchestrator.registry import MetadataRegistry

logger = logging.getLogger("VerifyRegistry")

async def run_test() -> bool:
    logger.info("[*] Running Registry Verification...")
    
    # 1. Initialize Registry
    registry = MetadataRegistry(auto_reload=True, reload_interval=1)
    await registry.initialize()
    
    # Check count validation
    h = registry.health()
    if h["status"] != "healthy" or h["workflows_count"] == 0:
        logger.error("[-] Health check failed or workflows not loaded")
        return False
        
    original_hash = h["version"]
    logger.info(f"[+] Loaded {h['workflows_count']} workflows. Version hash: {original_hash}")
    
    # 2. Verify hot-reload
    # Create a temporary workflow config file, initialize reload check, and check hash modification
    wf_dir = Path(__file__).parent.parent.parent / "workflows"
    temp_wf = wf_dir / "temp_hot_reload_test.yaml"
    
    try:
        temp_wf.write_text("""
name: temp_hot_reload_test
version: 1.0.0
description: Temporary hot reload test workflow
steps:
  - id: step_temp
    action: pass_through
    input:
      data: "hello"
outputs: {}
""", encoding="utf-8")
        
        # Trigger reload check (polls filesystem)
        await registry.reload()
        
        new_health = registry.health()
        new_hash = new_health["version"]
        logger.info(f"[+] Registry reloaded. New version hash: {new_hash}")
        
        if new_hash == original_hash:
            logger.error("[-] Auto-reload failed to update registry version hash")
            return False
            
        # Verify the new workflow is accessible
        wf = registry.get_workflow("temp_hot_reload_test")
        if not wf or wf.name != "temp_hot_reload_test":
            logger.error("[-] Failed to retrieve new workflow config after auto-reload")
            return False
            
        logger.info("[+] Auto-reload hot-swap verified successfully!")
        
    finally:
        # Clean up temp file
        if temp_wf.exists():
            temp_wf.unlink()
            
        # Restore registry
        await registry.reload()
        
    logger.info("[+] Registry Verification: PASSED")
    return True
