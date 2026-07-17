import logging
from typing import Dict, Any, List, Optional
from orchestrator.compiler import WorkflowDefinition

logger = logging.getLogger(__name__)

class ExecutionNode:
    """Represents a single step node in the workflow execution plan."""
    def __init__(self, step_data: Dict[str, Any]):
        self.node_id = step_data.get("id", "")
        self.action = step_data.get("action")
        self.agent = step_data.get("agent")
        self.foreach = step_data.get("foreach")
        self.parallel = step_data.get("parallel", False)
        self.steps = step_data.get("steps", [])  # for nested parallel steps
        self.input_template = step_data.get("input", {})
        self.output_var = step_data.get("output_var")
        self.continue_on_failure = step_data.get("continue_on_failure", False)
        
        # Policy definitions (timeouts, retries)
        self.retry_policy = step_data.get("retry", {})
        self.timeout = step_data.get("timeout", 300)
        self.priority = step_data.get("priority", 0)
        
        # Extracted list of dependencies (step IDs this node relies on)
        self.dependencies: List[str] = []

class ExecutionPlan:
    """Maintains step execution dependencies and graph traversal logic."""
    def __init__(self, workflow_id: str, nodes: Dict[str, ExecutionNode]):
        self.workflow_id = workflow_id
        self.nodes = nodes

class ExecutionPlanner:
    """Builds graph-based execution plan models from WorkflowDefinitions."""
    @classmethod
    def build_plan(cls, workflow_def: WorkflowDefinition) -> ExecutionPlan:
        nodes = {}
        for step in workflow_def.steps:
            node = ExecutionNode(step)
            nodes[node.node_id] = node
            
        # Parse step dependency relationships
        import json
        import re
        for node_id, node in nodes.items():
            # Dependencies can be identified from step outputs inputs references: steps.STEP_ID.output
            node_str = json.dumps(node.input_template)
            refs = re.findall(r"steps\.([a-zA-Z0-9_-]+)\.output", node_str)
            for ref in refs:
                if ref in nodes and ref not in node.dependencies:
                    node.dependencies.append(ref)
                    
            # If the node has sub-steps, add those sub-steps as dependencies
            for sub_step in node.steps:
                sub_id = sub_step.get("id")
                if sub_id and sub_id not in node.dependencies:
                    node.dependencies.append(sub_id)

        # Merge error handling configs into retry policies
        for eh in workflow_def.error_handling:
            target_step = eh.get("step")
            if target_step in nodes:
                node = nodes[target_step]
                node.retry_policy["max_attempts"] = max(
                    node.retry_policy.get("max_attempts", 1),
                    eh.get("retry_count", 0) + 1
                )
                if eh.get("on_failure") == "log_and_continue":
                    node.continue_on_failure = True
                    
        return ExecutionPlan(workflow_def.workflow_id, nodes)
