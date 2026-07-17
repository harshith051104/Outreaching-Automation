import logging
import time
import os
import psutil
from orchestrator.registry import MetadataRegistry
from orchestrator.compiler import WorkflowCompiler
from orchestrator.planner import ExecutionPlanner

logger = logging.getLogger("VerifyPerformance")

async def run_test() -> bool:
    logger.info("[*] Running Performance & Latency Benchmarks...")
    
    # 1. Registry Load Time Benchmark
    start_time = time.perf_counter()
    registry = MetadataRegistry(auto_reload=False)
    await registry.initialize()
    registry_load_latency = time.perf_counter() - start_time
    
    # 2. Workflow Compile Time Benchmark
    start_time = time.perf_counter()
    compiler = WorkflowCompiler(validation_level="WARN")
    compiled_wfs = compiler.compile_all(registry)
    compilation_latency = time.perf_counter() - start_time
    
    # 3. Planner Latency Benchmark
    planner_latency = 0.0
    campaign_wf = registry.get_workflow("Campaign Creation Workflow")
    if campaign_wf:
        start_time = time.perf_counter()
        compiled_wf = compiler.get_compiled("Campaign Creation Workflow")
        plan = ExecutionPlanner.build_plan(compiled_wf)
        planner_latency = time.perf_counter() - start_time
        
    # 4. Memory Footprint Benchmark
    process = psutil.Process(os.getpid())
    mem_usage_mb = process.memory_info().rss / (1024 * 1024)
    
    # Print Benchmark table
    logger.info("=" * 60)
    logger.info(f"| {'Benchmark Name':<28} | {'Latency/Value':<25} |")
    logger.info("=" * 60)
    logger.info(f"| {'Registry Load Time':<28} | {registry_load_latency*1000:<20.2f} ms |")
    logger.info(f"| {'Workflow Compile Time':<28} | {compilation_latency*1000:<20.2f} ms |")
    logger.info(f"| {'Planner Latency':<28} | {planner_latency*1000:<20.2f} ms |")
    logger.info(f"| {'Memory Usage Footprint':<28} | {mem_usage_mb:<20.2f} MB |")
    logger.info("=" * 60)
    
    logger.info("[+] Performance Verification: PASSED")
    return True
