import uuid
import time
from typing import Dict, Any, Optional

class ExecutionContext:
    """Immutable parameter container that holds metadata, configurations and variables for step executions."""
    def __init__(
        self,
        campaign: Optional[Dict[str, Any]] = None,
        lead: Optional[Dict[str, Any]] = None,
        user: Optional[Dict[str, Any]] = None,
        variables: Optional[Dict[str, Any]] = None,
        llm_provider: Optional[str] = None,
        vector_memory: Optional[Any] = None,
        cache: Optional[Any] = None,
        settings: Optional[Dict[str, Any]] = None,
        execution_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        timestamps: Optional[Dict[str, float]] = None
    ):
        self.campaign = campaign or {}
        self.lead = lead or {}
        self.user = user or {}
        self.variables = variables or {}
        self.llm_provider = llm_provider
        self.vector_memory = vector_memory
        self.cache = cache
        self.settings = settings or {}
        self.execution_id = execution_id or f"exec_{uuid.uuid4()}"
        self.correlation_id = correlation_id or f"corr_{uuid.uuid4()}"
        
        self.timestamps = timestamps or {
            "created_at": time.time()
        }

    def with_variable(self, name: str, value: Any) -> "ExecutionContext":
        """Return a new copy of ExecutionContext with the updated variables."""
        new_vars = {**self.variables, name: value}
        return ExecutionContext(
            campaign=self.campaign,
            lead=self.lead,
            user=self.user,
            variables=new_vars,
            llm_provider=self.llm_provider,
            vector_memory=self.vector_memory,
            cache=self.cache,
            settings=self.settings,
            execution_id=self.execution_id,
            correlation_id=self.correlation_id,
            timestamps=self.timestamps
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "correlation_id": self.correlation_id,
            "campaign": self.campaign,
            "lead": self.lead,
            "user": self.user,
            "variables": self.variables,
            "llm_provider": self.llm_provider,
            "settings": self.settings,
            "timestamps": self.timestamps
        }
