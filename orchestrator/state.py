import uuid
import time
from typing import Dict, Any, List, Optional

class RuntimeState:
    """Contains loaded engine services and static context references."""
    def __init__(self, registry: Any, compiler: Any, planner: Any, dispatcher: Any):
        self.registry = registry
        self.compiler = compiler
        self.planner = planner
        self.dispatcher = dispatcher
        self.initialized = True

class ExecutionState:
    """Tracks dynamic runtime parameters of a single active workflow execution."""
    def __init__(self, workflow_id: str, workflow_version: str):
        self.workflow_run_id = f"wrun_{uuid.uuid4()}"
        self.workflow_id = workflow_id
        self.workflow_version = workflow_version
        
        self.current_node: Optional[str] = None
        self.completed_nodes: List[str] = []
        self.failed_nodes: List[str] = []
        self.retries: Dict[str, int] = {}
        self.variables: Dict[str, Any] = {}
        self.artifacts: List[Dict[str, Any]] = []
        
        self.status = "CREATED"  # CREATED, VALIDATED, READY, RUNNING, WAITING, PAUSED, FAILED, COMPLETED, CANCELLED
        self.error: Optional[str] = None
        self.started_at = time.time()
        self.ended_at: Optional[float] = None

    def update_status(self, new_status: str) -> None:
        self.status = new_status
        if new_status in ["COMPLETED", "FAILED", "CANCELLED"]:
            self.ended_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_run_id": self.workflow_run_id,
            "workflow_id": self.workflow_id,
            "workflow_version": self.workflow_version,
            "current_node": self.current_node,
            "completed_nodes": self.completed_nodes,
            "failed_nodes": self.failed_nodes,
            "retries": self.retries,
            "variables": self.variables,
            "artifacts": self.artifacts,
            "status": self.status,
            "error": self.error,
            "started_at": self.started_at,
            "ended_at": self.ended_at
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExecutionState":
        state = cls(data["workflow_id"], data["workflow_version"])
        state.workflow_run_id = data["workflow_run_id"]
        state.current_node = data.get("current_node")
        state.completed_nodes = data.get("completed_nodes", [])
        state.failed_nodes = data.get("failed_nodes", [])
        state.retries = data.get("retries", {})
        state.variables = data.get("variables", {})
        state.artifacts = data.get("artifacts", [])
        state.status = data.get("status", "CREATED")
        state.error = data.get("error")
        state.started_at = data.get("started_at", time.time())
        state.ended_at = data.get("ended_at")
        return state
