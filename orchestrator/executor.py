import logging
import asyncio
import time
import re
import uuid
from typing import Dict, Any, List, Optional
from orchestrator.planner import ExecutionPlan, ExecutionNode
from orchestrator.context import ExecutionContext
from orchestrator.state import ExecutionState
from orchestrator.skill_runtime import SkillRuntime
from orchestrator.persistence import PersistenceService

logger = logging.getLogger(__name__)

class WorkflowExecutor:
    """Core runtime engine responsible for traversing the ExecutionPlan and running steps with template resolution."""
    def __init__(
        self,
        skill_runtime: SkillRuntime,
        dispatcher: Any,
        persistence: PersistenceService,
        event_bus: Optional[Any] = None
    ):
        self.skill_runtime = skill_runtime
        self.dispatcher = dispatcher
        self.persistence = persistence
        self.event_bus = event_bus

    async def execute(
        self,
        plan: ExecutionPlan,
        inputs: Dict[str, Any],
        state: ExecutionState,
        context: ExecutionContext
    ) -> Dict[str, Any]:
        logger.info(f"WorkflowExecutor: Starting execution run {state.workflow_run_id} for workflow '{plan.workflow_id}'")
        state.update_status("RUNNING")
        
        # Build resolve context (contains inputs and intermediate step outputs)
        resolver_ctx = {
            "inputs": inputs,
            "_step_outputs": {},
            "steps": {}
        }
        
        # Load variables from state if resuming from a snapshot
        if state.variables:
            resolver_ctx.update(state.variables)
            
        # Standard event emission
        if self.event_bus:
            await self.event_bus.publish("workflow.started", {
                "workflow_run_id": state.workflow_run_id,
                "workflow_id": state.workflow_id
            })

        # Run nodes based on topological sort (sequential / parallel / conditional)
        # For compatibility with legacy linear step executor, we iterate over plan.nodes in insertion order
        for node_id, node in plan.nodes.items():
            state.current_node = node_id
            
            # Persist state snapshot
            await self._persist_state(state)
            
            # Emit step.started event
            if self.event_bus:
                await self.event_bus.publish("step.started", {
                    "workflow_run_id": state.workflow_run_id,
                    "workflow_id": state.workflow_id,
                    "step_id": node_id
                })

            attempt = 0
            max_attempts = 1
            delay_policy = "fixed"
            backoff_delay = 1.0
            
            if node.retry_policy:
                max_attempts = max(1, node.retry_policy.get("max_attempts", 1))
                delay_policy = node.retry_policy.get("delay", "fixed")
                backoff_delay = node.retry_policy.get("backoff_delay", 1.0)
                
            success = False
            result = None
            last_err = None
            
            # Execute step with retries
            while attempt < max_attempts:
                try:
                    result = await self._execute_node(node, resolver_ctx, state, context)
                    success = True
                    break
                except Exception as e:
                    last_err = e
                    attempt += 1
                    state.retries[node_id] = attempt
                    logger.error(f"WorkflowExecutor: Node '{node_id}' failed on attempt {attempt}: {e}")
                    
                    if attempt < max_attempts:
                        # Implement retry delay
                        sleep_time = backoff_delay
                        if delay_policy == "exponential":
                            sleep_time = backoff_delay * (2 ** (attempt - 1))
                        await asyncio.sleep(sleep_time)
                        
            if not success:
                logger.error(f"WorkflowExecutor: Node '{node_id}' permanently failed after {max_attempts} attempts.")
                state.failed_nodes.append(node_id)
                
                # Emit step.failed event
                if self.event_bus:
                    await self.event_bus.publish("step.failed", {
                        "workflow_run_id": state.workflow_run_id,
                        "workflow_id": state.workflow_id,
                        "step_id": node_id,
                        "error": str(last_err)
                    })

                if node.continue_on_failure:
                    logger.warning(f"WorkflowExecutor: Node '{node_id}' continuing on failure (continue_on_failure=True)")
                    result = {"error": str(last_err), "skipped": True}
                else:
                    state.update_status("FAILED")
                    state.error = str(last_err)
                    await self._persist_state(state)
                    
                    # Execute error handlers (mark failed, fallback tavily)
                    # For backward compatibility, search campaign error handling blocks
                    error_handlers = self._get_error_handlers(plan, node_id)
                    if error_handlers:
                        for handler in error_handlers:
                            await self._execute_error_handler(handler, resolver_ctx, last_err)
                    
                    if self.event_bus:
                        await self.event_bus.publish("workflow.failed", {
                            "workflow_run_id": state.workflow_run_id,
                            "workflow_id": state.workflow_id,
                            "error": str(last_err)
                        })
                    raise last_err
            else:
                state.completed_nodes.append(node_id)
                # Emit step.completed event
                if self.event_bus:
                    await self.event_bus.publish("step.completed", {
                        "workflow_run_id": state.workflow_run_id,
                        "workflow_id": state.workflow_id,
                        "step_id": node_id
                    })

            # Store result in execution context
            resolver_ctx["_step_outputs"][node_id] = result
            resolver_ctx["steps"][node_id] = {"output": result}
            
            if node.output_var:
                resolver_ctx[node.output_var] = result
                state.variables[node.output_var] = result

            # Update consumer lineage of existing dependencies
            for dep in node.dependencies:
                for art in state.artifacts:
                    if art.get("producer") == dep:
                        art["consumer"] = node_id

            # Record artifact in state with full lineage
            artifact_id = f"art_{uuid.uuid4()}"
            artifact_record = {
                "artifact_id": artifact_id,
                "workflow_run_id": state.workflow_run_id,
                "execution_id": state.workflow_run_id,
                "producer": node_id,
                "consumer": None,
                "step_id": node_id,
                "payload": result,
                "timestamp": time.time()
            }
            state.artifacts.append(artifact_record)
            
            # Save artifact to database via PersistenceService
            if self.persistence:
                await self.persistence.save_artifact(
                    artifact_id=artifact_id,
                    workflow_run_id=state.workflow_run_id,
                    step_id=node_id,
                    payload=result,
                    metadata={
                        "workflow_id": state.workflow_id,
                        "producer": node_id,
                        "consumer": None,
                        "execution_id": state.workflow_run_id
                    }
                )

        state.update_status("COMPLETED")
        await self._persist_state(state)
        
        if self.event_bus:
            await self.event_bus.publish("workflow.completed", {
                "workflow_run_id": state.workflow_run_id,
                "workflow_id": state.workflow_id
            })

        # Resolve output expressions
        # Exposes workflow config outputs
        wf_outputs = resolver_ctx["_step_outputs"]
        # Find outputs template in plan/workflow
        return self._resolve_outputs(resolver_ctx.get("outputs", {}), resolver_ctx)

    async def _execute_node(
        self,
        node: ExecutionNode,
        resolver_ctx: Dict[str, Any],
        state: ExecutionState,
        context: ExecutionContext
    ) -> Any:
        # 1. Resolve foreach iteration
        if node.foreach:
            items = self._resolve_value(node.foreach, resolver_ctx)
            if not isinstance(items, list):
                items = [items] if items else []
            results = []
            for item in items:
                # Copy and enrich context for foreach
                item_ctx = {**resolver_ctx, "item": item, "reply_item": item}
                # Create a temporary execution node copy without the foreach flag
                temp_node = ExecutionNode({
                    "id": node.node_id,
                    "action": node.action,
                    "agent": node.agent,
                    "input": node.input_template,
                    "output_var": node.output_var
                })
                res = await self._execute_node(temp_node, item_ctx, state, context)
                results.append(res)
            return results

        # 2. Resolve parallel steps
        if node.parallel:
            tasks = []
            for sub_step in node.steps:
                sub_node = ExecutionNode(sub_step)
                tasks.append(self._execute_node(sub_node, resolver_ctx, state, context))
            return await asyncio.gather(*tasks)

        # 3. Resolve template input variables
        resolved_inputs = self._resolve_template(node.input_template, resolver_ctx)

        # 4. Check Agent Reference
        if node.agent:
            agent_name = node.agent
            logger.info(f"WorkflowExecutor: Executing agent '{agent_name}'")
            
            # Check dispatcher for agent tool action (legacy python functions registered as tools)
            if self.dispatcher.has_tool(agent_name):
                tool_res = await self.dispatcher.execute(
                    tool_name=agent_name,
                    inputs=resolved_inputs,
                    context=resolver_ctx,
                    workflow_run_id=state.workflow_run_id
                )
                if not tool_res.success:
                    raise RuntimeError(f"Agent tool run failed: {tool_res.error}")
                return tool_res.output
            
            # Dynamic fallback: execute as generic LLM agent runner
            # We can invoke it using a dynamically registered tool wrapper or delegate directly
            if self.dispatcher.has_tool("run_generic_agent"):
                tool_res = await self.dispatcher.execute(
                    tool_name="run_generic_agent",
                    inputs={"agent_name": agent_name, "inputs": resolved_inputs},
                    context=resolver_ctx,
                    workflow_run_id=state.workflow_run_id
                )
                return tool_res.output
            raise ValueError(f"Agent executor or dynamic tool not found for agent '{agent_name}'")

        # 5. Check Action/Skill
        action = node.action
        if not action:
            raise ValueError(f"Step '{node.node_id}' has neither agent nor action.")

        # Built-ins
        if action == "pass_through":
            return self._resolve_value(resolved_inputs.get("data"), resolver_ctx)
        elif action == "validate":
            return {"valid": True}
        elif action == "conditional":
            condition = resolved_inputs.get("condition", "")
            if self._evaluate_condition(condition, resolver_ctx):
                true_node = ExecutionNode({"id": f"{node.node_id}_true", "action": resolved_inputs.get("true_branch")})
                return await self._execute_node(true_node, resolver_ctx, state, context)
            elif "false_branch" in resolved_inputs:
                false_node = ExecutionNode({"id": f"{node.node_id}_false", "action": resolved_inputs.get("false_branch")})
                return await self._execute_node(false_node, resolver_ctx, state, context)
            return None

        # Route through SkillRuntime (which delegates to ToolDispatcher or LLM dynamic skill fallback)
        return await self.skill_runtime.execute(
            skill_name=action,
            inputs=resolved_inputs,
            context=context.with_variable("steps", resolver_ctx.get("steps")),
            workflow_run_id=state.workflow_run_id
        )

    async def _persist_state(self, state: ExecutionState) -> None:
        if self.persistence:
            await self.persistence.save_workflow_run(state.workflow_run_id, state.to_dict())

    # --- Legacy Compatibility Template Resolver Methods ---
    def _resolve_value(self, value: Any, ctx: Dict) -> Any:
        if isinstance(value, str):
            return self._resolve_template_string(value, ctx)
        elif isinstance(value, dict):
            return {k: self._resolve_value(v, ctx) for k, v in value.items()}
        elif isinstance(value, list):
            return [self._resolve_value(v, ctx) for v in value]
        return value

    def _resolve_template_string(self, template: str, ctx: Dict) -> Any:
        exact_match = re.match(r"^\{\{([^}]+)\}\}$", template.strip())
        if exact_match:
            path = exact_match.group(1).strip()
            parts = path.split(".")
            value = ctx
            for part in parts:
                if isinstance(value, dict):
                    val = value.get(part, None)
                    if val is None and part == "investor_focus":
                        val = value.get("focus", None)
                    value = val
                elif isinstance(value, list):
                    try:
                        idx = int(part)
                        if 0 <= idx < len(value):
                            value = value[idx]
                        else:
                            value = None
                    except ValueError:
                        return ""
                else:
                    return ""
            return value if value is not None else ""

        def replace_var(match):
            path = match.group(1).strip()
            parts = path.split(".")
            value = ctx
            for part in parts:
                if isinstance(value, dict):
                    val = value.get(part, "")
                    if (val == "" or val is None) and part == "investor_focus":
                        val = value.get("focus", "")
                    value = val
                elif isinstance(value, list):
                    try:
                        idx = int(part)
                        if 0 <= idx < len(value):
                            value = value[idx]
                        else:
                            value = ""
                    except ValueError:
                        return ""
                else:
                    return ""
            return str(value) if value is not None else ""

        return re.sub(r"\{\{([^}]+)\}\}", replace_var, template)

    def _resolve_template(self, template: Any, ctx: Dict) -> Any:
        return self._resolve_value(template, ctx)

    def _resolve_outputs(self, outputs: Dict, ctx: Dict) -> Dict:
        result = {}
        for key, value in outputs.items():
            result[key] = self._resolve_value(value, ctx)
        return result

    def _evaluate_condition(self, condition: str, ctx: Dict) -> bool:
        condition = condition.strip()
        for op, eval_fn in [
            (">=", lambda a, b: float(a) >= float(b)),
            ("<=", lambda a, b: float(a) <= float(b)),
            (">", lambda a, b: float(a) > float(b)),
            ("<", lambda a, b: float(a) < float(b)),
            ("==", lambda a, b: (float(a) == float(b)) 
                                if (str(a).replace('.','',1).lstrip('-').isdigit() and 
                                    str(b).replace('.','',1).lstrip('-').isdigit()) 
                                else str(a) == str(b)),
        ]:
            if op in condition:
                parts = condition.split(op)
                if len(parts) == 2:
                    try:
                        left = self._resolve_value(parts[0].strip(), ctx)
                        right = self._resolve_value(parts[1].strip(), ctx)
                        return eval_fn(left, right)
                    except Exception as e:
                        logger.error(f"Failed to evaluate operator condition: {e}")
                        return False
        resolved = self._resolve_value(condition, ctx)
        if isinstance(resolved, str):
            return resolved.lower() in ["true", "yes", "1"]
        return bool(resolved)

    def _get_error_handlers(self, plan: ExecutionPlan, step_id: str) -> List[Dict]:
        # Handled in planner compiling, but kept here for compatibility
        return []

    async def _execute_error_handler(self, handler: Dict, ctx: Dict, error: Exception) -> None:
        action = handler.get("on_failure")
        if action == "fallback_tavily":
            try:
                from app.services.tavily_service import TavilyService
                tavily = TavilyService()
                query = ctx.get("inputs", {}).get("company_name", "") or ctx.get("inputs", {}).get("company", "") or "B2B Outreach"
                results = await tavily.search(query=f"company details {query}")
                ctx["fallback_research_data"] = results
                logger.info(f"Fallback Tavily research completed for query '{query}'")
            except Exception as exc:
                logger.error(f"Fallback Tavily research failed: {exc}")
        elif action == "mark_failed":
            try:
                from app.config.mongodb_config import get_database
                from datetime import datetime, timezone
                db = await get_database()
                lead_id = ctx.get("inputs", {}).get("lead_id") or ctx.get("item", {}).get("id")
                if lead_id:
                    await db.leads.update_one(
                        {"id": lead_id},
                        {"$set": {"status": "failed", "error_message": str(error), "updated_at": datetime.now(timezone.utc)}}
                    )
                    logger.info(f"Lead {lead_id} marked as failed due to error: {error}")
            except Exception as exc:
                logger.error(f"Failed to mark entity as failed: {exc}")
