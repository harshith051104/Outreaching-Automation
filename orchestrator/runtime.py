import logging
from typing import Dict, Any, Optional
from orchestrator.registry import MetadataRegistry
from orchestrator.compiler import WorkflowCompiler
from orchestrator.planner import ExecutionPlanner
from orchestrator.executor import WorkflowExecutor
from orchestrator.context import ExecutionContext
from orchestrator.state import ExecutionState
from orchestrator.event_bus import EventBus
from orchestrator.persistence import PersistenceService

logger = logging.getLogger(__name__)

class WorkflowRuntime:
    """Stateless WorkflowRuntime orchestrating the compilation, planning, and execution phases of workflows."""
    def __init__(
        self,
        registry: MetadataRegistry,
        compiler: WorkflowCompiler,
        planner: ExecutionPlanner,
        executor: WorkflowExecutor,
        event_bus: EventBus,
        persistence: PersistenceService,
        llm_interface: Any
    ):
        self.registry = registry
        self.compiler = compiler
        self.planner = planner
        self.executor = executor
        self.event_bus = event_bus
        self.persistence = persistence
        self.llm_interface = llm_interface

    async def run(
        self,
        workflow_id: str,
        inputs: Dict[str, Any],
        campaign: Optional[Dict[str, Any]] = None,
        lead: Optional[Dict[str, Any]] = None,
        user: Optional[Dict[str, Any]] = None,
        settings: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Compile, plan, and execute a workflow with clean parameter decoupling."""
        # 1. Retrieve compiled workflow definition
        wf_def = self.compiler.get_compiled(workflow_id)
        if not wf_def:
            # Try lazy compilation of target workflow if not pre-compiled
            raw_wf = self.registry.get_workflow(workflow_id)
            if not raw_wf:
                raise ValueError(f"WorkflowRuntime: Workflow '{workflow_id}' not found in registry")
            wf_def = self.compiler.compile(raw_wf, self.registry)
            
        # 2. Build execution plan
        plan = self.planner.build_plan(wf_def)

        # 3. Instantiate state and context
        state = ExecutionState(workflow_id=workflow_id, workflow_version=wf_def.workflow_version)
        context = ExecutionContext(
            campaign=campaign,
            lead=lead,
            user=user,
            variables=inputs,
            settings=settings,
            correlation_id=correlation_id
        )

        # 4. Trigger executor
        try:
            result = await self.executor.execute(plan, inputs, state, context)
            return result
        except Exception as e:
            logger.error(f"WorkflowRuntime: Run failed for workflow '{workflow_id}': {e}")
            raise e

    async def resume_run(self, workflow_run_id: str, campaign: Dict, lead: Dict, user: Dict) -> Dict[str, Any]:
        """Resume a suspended or paused workflow run from a database snapshot state."""
        if not self.persistence:
            raise RuntimeError("PersistenceService not initialized; cannot resume workflow runs")
            
        run_data = await self.persistence.get_workflow_run(workflow_run_id)
        if not run_data:
            raise ValueError(f"WorkflowRuntime: Workflow run snapshot '{workflow_run_id}' not found")
            
        state = ExecutionState.from_dict(run_data)
        if state.status not in ["PAUSED", "WAITING", "FAILED"]:
            logger.warning(f"WorkflowRuntime: Resuming a run in status '{state.status}' might cause issues")

        wf_def = self.compiler.get_compiled(state.workflow_id)
        if not wf_def:
            raw_wf = self.registry.get_workflow(state.workflow_id)
            if not raw_wf:
                raise ValueError(f"WorkflowRuntime: Workflow '{state.workflow_id}' not found in registry")
            wf_def = self.compiler.compile(raw_wf, self.registry)

        plan = self.planner.build_plan(wf_def)
        context = ExecutionContext(
            campaign=campaign,
            lead=lead,
            user=user,
            variables=state.variables,
            correlation_id=state.workflow_run_id
        )
        
        # Resume executor starting from the paused node
        result = await self.executor.execute(plan, state.variables, state, context)
        return result
