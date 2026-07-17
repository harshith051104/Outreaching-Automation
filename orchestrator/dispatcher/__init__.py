import logging
import time
import uuid
import asyncio
from typing import Dict, Any, List, Optional, Callable

from .mongodb import register_mongodb_tools
from .qdrant import register_qdrant_tools
from .gmail import register_gmail_tools
from .websocket import register_websocket_tools
from .spam import register_spam_tools

logger = logging.getLogger(__name__)

class ToolResult:
    """Standardized output container for all tool executions."""
    def __init__(
        self,
        success: bool,
        output: Any = None,
        artifacts: Optional[List[Dict[str, Any]]] = None,
        duration: float = 0.0,
        logs: Optional[List[str]] = None,
        retry_count: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ):
        self.success = success
        self.output = output
        self.artifacts = artifacts or []
        self.duration = duration
        self.logs = logs or []
        self.retry_count = retry_count
        self.metadata = metadata or {}
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "output": self.output,
            "artifacts": self.artifacts,
            "duration": self.duration,
            "logs": self.logs,
            "retry_count": self.retry_count,
            "metadata": self.metadata,
            "error": self.error
        }

class ToolDispatcher:
    """Extensible, plugin-based registry and execution coordinator for all platform tools."""
    def __init__(self, registry: Any, persistence: Any, event_bus: Optional[Any] = None):
        self.registry = registry
        self.persistence = persistence
        self.event_bus = event_bus
        self._handlers: Dict[str, Callable[[Dict[str, Any], Dict[str, Any]], Any]] = {}

    def register(self, tool_name: str, handler: Callable[[Dict[str, Any], Dict[str, Any]], Any]) -> None:
        """Register a tool handler function canonically, rejecting duplicate configurations."""
        if tool_name in self._handlers:
            existing_handler = self._handlers[tool_name]
            if existing_handler == handler:
                # Silently ignore identical duplicate registration
                return
            raise ValueError(
                f"ToolDispatcher: Duplicate tool registration detected for '{tool_name}' "
                f"with a different handler function."
            )
        self._handlers[tool_name] = handler
        logger.info(f"ToolDispatcher: Registered tool '{tool_name}'")

    def has_tool(self, tool_name: str) -> bool:
        return tool_name in self._handlers

    async def execute(
        self,
        tool_name: str,
        inputs: Dict[str, Any],
        context: Dict[str, Any],
        workflow_run_id: str = "local"
    ) -> ToolResult:
        """Execute a tool with input schema validation, latency measurement, retries and logging."""
        tool_run_id = f"trun_{uuid.uuid4()}"
        start_time = time.time()
        
        # 1. Resolve handler
        handler = self._handlers.get(tool_name)
        if not handler:
            return ToolResult(
                success=False,
                error=f"Tool '{tool_name}' not registered in dispatcher",
                duration=0.0
            )

        # 2. Schema Validation (from registry)
        tool_config = self.registry.get_tool(tool_name)
        if tool_config:
            is_valid, err_msg = tool_config.validate_input(inputs)
            if not is_valid:
                logger.error(f"ToolDispatcher: Input validation failed for '{tool_name}': {err_msg}")
                return ToolResult(
                    success=False,
                    error=f"Input validation failed: {err_msg}",
                    duration=0.0
                )

        # Emit tool.started event
        if self.event_bus:
            await self.event_bus.publish(
                topic="tool.started",
                event_data={
                    "tool_run_id": tool_run_id,
                    "workflow_run_id": workflow_run_id,
                    "tool_name": tool_name,
                    "inputs": inputs
                }
            )

        # 3. Execution & Retry strategies
        max_attempts = 1
        delay_policy = "fixed"
        backoff_delay = 1.0

        if tool_config and tool_config.retry_strategy:
            max_attempts = max(1, tool_config.retry_strategy.get("max_attempts", 1))
            delay_policy = tool_config.retry_strategy.get("delay", "fixed")
            backoff_delay = tool_config.retry_strategy.get("backoff_delay", 1.0)

        attempt = 0
        success = False
        output = None
        error_msg = None
        logs = []

        while attempt < max_attempts:
            attempt_start = time.time()
            try:
                # Execute the handler (handlers can be coroutines or plain functions)
                import inspect
                if inspect.iscoroutinefunction(handler):
                    output = await handler(inputs, context)
                else:
                    output = handler(inputs, context)
                success = True
                break
            except Exception as exc:
                error_msg = str(exc)
                logs.append(f"Attempt {attempt + 1} failed: {error_msg}")
                logger.warning(f"ToolDispatcher: Tool '{tool_name}' failed on attempt {attempt + 1}: {exc}")
                attempt += 1
                if attempt < max_attempts:
                    # Exponential or fixed backoff wait
                    sleep_time = backoff_delay
                    if delay_policy == "exponential":
                        sleep_time = backoff_delay * (2 ** (attempt - 1))
                    await asyncio.sleep(sleep_time)

        duration = time.time() - start_time
        result = ToolResult(
            success=success,
            output=output if success else None,
            duration=duration,
            logs=logs,
            retry_count=attempt,
            error=None if success else error_msg
        )

        # 4. Telemetry logging to MongoDB via Persistence Service
        if self.persistence:
            await self.persistence.save_tool_run(
                tool_run_id=tool_run_id,
                workflow_run_id=workflow_run_id,
                tool_name=tool_name,
                inputs=inputs,
                result=result.to_dict(),
                duration=duration,
                retry_count=attempt,
                error=result.error
            )

        # 5. Emit event to Event Bus
        if self.event_bus:
            # Emit standard tool.executed event for compatibility
            await self.event_bus.publish(
                topic="tool.executed",
                event_data={
                    "tool_run_id": tool_run_id,
                    "workflow_run_id": workflow_run_id,
                    "tool_name": tool_name,
                    "success": success,
                    "duration": duration,
                    "error": result.error
                }
            )
            # Emit tool.finished event for strict observability sequencing
            await self.event_bus.publish(
                topic="tool.finished",
                event_data={
                    "tool_run_id": tool_run_id,
                    "workflow_run_id": workflow_run_id,
                    "tool_name": tool_name,
                    "success": success,
                    "duration": duration,
                    "error": result.error
                }
            )

        return result

def register_all_tools(dispatcher) -> None:
    """Register all built-in tool plugins into the dispatcher."""
    register_mongodb_tools(dispatcher)
    register_qdrant_tools(dispatcher)
    register_gmail_tools(dispatcher)
    register_websocket_tools(dispatcher)
    register_spam_tools(dispatcher)
