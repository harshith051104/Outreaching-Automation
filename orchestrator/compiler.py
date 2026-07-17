import logging
import time
import hashlib
import json
import re
from typing import Dict, List, Any, Optional
from orchestrator.registry import AgentConfig, SkillConfig, WorkflowConfig, ToolConfig

logger = logging.getLogger(__name__)

class WorkflowDefinition:
    """Compiled workflow definition with versioning, dependency tracking, and validation metadata."""
    def __init__(
        self,
        workflow_id: str,
        workflow_version: str,
        registry_version: str,
        compiled_hash: str,
        compiled_at: float,
        steps: List[Dict[str, Any]],
        outputs: Dict[str, Any],
        error_handling: List[Dict[str, Any]]
    ):
        self.workflow_id = workflow_id
        self.workflow_version = workflow_version
        self.registry_version = registry_version
        self.compiled_hash = compiled_hash
        self.compiled_at = compiled_at
        self.steps = steps
        self.outputs = outputs
        self.error_handling = error_handling

class WorkflowCompiler:
    """Compiles raw workflow configurations in-memory into executable WorkflowDefinitions."""
    def __init__(self, validation_level: Optional[str] = None):
        self._compiled_cache: Dict[str, WorkflowDefinition] = {}
        self.validation_level = validation_level
        if not self.validation_level:
            try:
                from pathlib import Path
                import yaml
                base = Path(__file__).parent.parent
                cfg_file = base / "orchestrator" / "config" / "orchestrator.yaml"
                if cfg_file.exists():
                    cfg = yaml.safe_load(cfg_file.read_text(encoding="utf-8")) or {}
                    self.validation_level = cfg.get("compiler", {}).get("validation_level", "STRICT")
            except Exception:
                pass
        if not self.validation_level:
            self.validation_level = "STRICT"

    def get_compiled(self, workflow_id: str) -> Optional[WorkflowDefinition]:
        return self._compiled_cache.get(workflow_id)

    def compile_all(self, registry_ref: Any) -> Dict[str, WorkflowDefinition]:
        """Compile all workflows in the registry."""
        registry_version = registry_ref.registry_version
        workflows = {}
        loaded_keys = list(registry_ref._workflows.keys())
        for wid in loaded_keys:
            raw_workflow = registry_ref.get_workflow(wid)
            if raw_workflow:
                try:
                    compiled = self.compile(raw_workflow, registry_ref)
                    self._compiled_cache[wid] = compiled
                    workflows[wid] = compiled
                except Exception as e:
                    logger.error(f"WorkflowCompiler: Failed to compile workflow '{wid}': {e}")
                    raise e
                    
        return workflows

    def compile(self, raw_wf: WorkflowConfig, registry_ref: Any) -> WorkflowDefinition:
        """Validate and compile a single raw workflow config."""
        logger.info(f"WorkflowCompiler: Compiling workflow '{raw_wf.name}'...")
        
        # 1. Validation checks
        self._validate_references(raw_wf, registry_ref)
        self._validate_dependencies(raw_wf)
        
        # 2. Compute compiled hash based on structural content
        serialized_struct = json.dumps({
            "name": raw_wf.name,
            "version": raw_wf.version,
            "steps": raw_wf.steps,
            "outputs": raw_wf.outputs,
            "error_handling": raw_wf.error_handling
        }, sort_keys=True)
        compiled_hash = hashlib.md5(serialized_struct.encode("utf-8")).hexdigest()
        
        compiled_wf = WorkflowDefinition(
            workflow_id=raw_wf.name,
            workflow_version=raw_wf.version,
            registry_version=registry_ref.registry_version,
            compiled_hash=compiled_hash,
            compiled_at=time.time(),
            steps=raw_wf.steps,
            outputs=raw_wf.outputs,
            error_handling=raw_wf.error_handling
        )
        
        logger.info(f"WorkflowCompiler: Compiled workflow '{raw_wf.name}' successfully. Hash={compiled_hash}")
        return compiled_wf

    def _validate_references(self, raw_wf: WorkflowConfig, registry_ref: Any) -> None:
        """Validate references to agents, skills, and variables."""
        for step in raw_wf.steps:
            step_id = step.get("id", "")
            agent = step.get("agent")
            action = step.get("action")
            
            # Verify Agent Reference
            if agent:
                clean_agent = agent.lower().replace("_agent", "")
                if not (registry_ref.get_agent(agent) or registry_ref.get_agent(clean_agent) or registry_ref.get_agent(f"{clean_agent}_agent")):
                    msg = f"Workflow '{raw_wf.name}': Step '{step_id}' references unknown agent '{agent}'"
                    if self.validation_level == "STRICT":
                        raise ValueError(msg)
                    else:
                        logger.warning(msg)
                    
            # Verify Action/Skill Reference
            if action:
                # Exclude built-in action commands
                builtins = ["conditional", "pass_through", "validate"]
                if action not in builtins:
                    clean_action = action.lower().replace("_skill", "")
                    has_skill = registry_ref.get_skill(action) or registry_ref.get_skill(clean_action) or registry_ref.get_skill(f"{clean_action}_skill")
                    has_tool = registry_ref.get_tool(action)
                    if not (has_skill or has_tool):
                        msg = f"Workflow '{raw_wf.name}': Step '{step_id}' references unknown action/skill '{action}'"
                        if self.validation_level == "STRICT":
                            raise ValueError(msg)
                        else:
                            logger.warning(msg)

    def _validate_dependencies(self, raw_wf: WorkflowConfig) -> None:
        """Build a dependency graph of steps and verify there are no circular dependencies."""
        step_ids = [step.get("id") for step in raw_wf.steps if step.get("id")]
        
        # 1. Build adjacency list of step dependencies
        adj_list: Dict[str, List[str]] = {sid: [] for sid in step_ids}
        
        for step in raw_wf.steps:
            step_id = step.get("id")
            if not step_id:
                continue
                
            # Scan step dict for input references to other steps: {{steps.STEP_ID.output}}
            step_str = json.dumps(step)
            # Find references using regex: steps\.([a-zA-Z0-9_-]+)\.output
            refs = re.findall(r"steps\.([a-zA-Z0-9_-]+)\.output", step_str)
            for ref in refs:
                if ref in adj_list and ref not in adj_list[step_id]:
                    # step_id depends on ref (ref must run before step_id)
                    adj_list[step_id].append(ref)
                    
            # Also check nested parallel steps
            if step.get("parallel"):
                for sub in step.get("steps", []):
                    sub_id = sub.get("id")
                    if sub_id:
                        adj_list[step_id].append(sub_id)

        # 2. Perform DFS to check for circular dependencies (cycles)
        visited = {} # state: 0=unvisited, 1=visiting, 2=visited
        for sid in step_ids:
            visited[sid] = 0
            
        def dfs(node: str) -> bool:
            visited[node] = 1 # visiting
            for neighbor in adj_list.get(node, []):
                if visited.get(neighbor, 0) == 1:
                    return True # Cycle detected
                elif visited.get(neighbor, 0) == 0:
                    if dfs(neighbor):
                        return True
            visited[node] = 2 # visited
            return False

        for sid in step_ids:
            if visited[sid] == 0:
                if dfs(sid):
                    raise ValueError(f"Workflow '{raw_wf.name}': Circular dependency detected around step '{sid}'")
