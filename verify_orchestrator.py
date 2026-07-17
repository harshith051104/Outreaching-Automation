import asyncio
import logging
import sys
import importlib.util
from pathlib import Path

# Setup logging to both console and file
log_file_path = Path(__file__).parent / "scratch" / "verification_run.log"
log_file_path.parent.mkdir(parents=True, exist_ok=True)

file_handler = logging.FileHandler(str(log_file_path), mode="w", encoding="utf-8")
file_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(file_handler)
root_logger.addHandler(console_handler)

logger = logging.getLogger("MasterVerification")

def load_test_module(name: str, file_path: Path):
    """Dynamically load verification modules from direct file paths to avoid namespace shadowing."""
    spec = importlib.util.spec_from_file_location(name, str(file_path))
    if not spec or not spec.loader:
        raise ImportError(f"Could not load spec for {file_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

async def run_master_verification():
    logger.info("=========================================================")
    logger.info("      STARTING ORCHESTRATOR PRODUCTION TEST SUITE        ")
    logger.info("=========================================================\n")

    base_dir = Path(__file__).parent / "tests" / "orchestrator"

    test_modules_info = [
        ("Metadata Registry & Hot-Swap Check", "verify_registry.py"),
        ("Compiler Strict/Warn & Graph Cycles", "verify_compiler.py"),
        ("Tool Dispatcher Canonical Registration", "verify_dispatcher.py"),
        ("Runtime State Transitions & Controls", "verify_runtime.py"),
        ("Persistence ID Consistency Checks", "verify_persistence.py"),
        ("EventBus Chronological Sequence Ordering", "verify_eventbus.py"),
        ("Skill Runtime Dynamic Prompt Render", "verify_skill_runtime.py"),
        ("Failure Handler & Backoff Retries", "verify_failures.py"),
        ("LLM Router 429 & Offline Fallbacks", "verify_llm_router.py"),
        ("Concurrency Context Variable Isolation", "verify_concurrency.py"),
        ("Execution Checkpoint Snapshot & Resume", "verify_resume.py"),
        ("End-to-End Workflow Execution Run", "verify_end_to_end.py"),
        ("Performance & Memory Benchmarks", "verify_performance.py"),
    ]

    results = []
    
    for name, filename in test_modules_info:
        file_path = base_dir / filename
        try:
            logger.info(f"\n---> Starting test: '{name}'")
            # Dynamically load the module
            module = load_test_module(filename.replace(".py", ""), file_path)
            success = await module.run_test()
            results.append((name, "PASSED" if success else "FAILED"))
        except Exception as e:
            logger.exception(f"[-] Test '{name}' crashed with exception: {e}")
            results.append((name, "CRASHED"))

    # Print final summary table
    logger.info("\n" + "=" * 65)
    logger.info(f"| {'Verification Suite Name':<40} | {'Status':<18} |")
    logger.info("=" * 65)
    
    passed_count = 0
    for name, status in results:
        logger.info(f"| {name:<40} | {status:<18} |")
        if status == "PASSED":
            passed_count += 1
            
    logger.info("=" * 65)
    logger.info(f"Summary: {passed_count}/{len(test_modules_info)} Suites Passed.\n")
    
    if passed_count != len(test_modules_info):
        logger.error("[-] Production Verification: FAILED")
        sys.exit(1)
    else:
        logger.info("[+] Production Verification: ALL PASSED")
        sys.exit(0)

if __name__ == "__main__":
    asyncio.run(run_master_verification())
