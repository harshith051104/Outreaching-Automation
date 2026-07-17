import logging
import json
import re
from typing import Dict, Any, Optional
from orchestrator.registry import SkillConfig
from orchestrator.context import ExecutionContext

logger = logging.getLogger(__name__)

class SkillRuntime:
    """Coordinates prompt rendering, LLM inference, tool execution, and output extraction for skills."""
    def __init__(self, registry: Any, dispatcher: Any, llm_interface: Any):
        self.registry = registry
        self.dispatcher = dispatcher
        self.llm_interface = llm_interface

    async def execute(self, skill_name: str, inputs: Dict[str, Any], context: ExecutionContext, workflow_run_id: str = "local") -> Any:
        # 1. Resolve skill config
        skill = self.registry.get_skill(skill_name)
        if not skill:
            # Fallback: if the action is registered directly in the dispatcher, execute it
            if self.dispatcher.has_tool(skill_name):
                logger.info(f"SkillRuntime: Direct tool dispatch for unregistered skill/tool '{skill_name}'")
                result = await self.dispatcher.execute(
                    tool_name=skill_name,
                    inputs=inputs,
                    context=context.to_dict(),
                    workflow_run_id=workflow_run_id
                )
                if not result.success:
                    raise RuntimeError(f"Tool execution failed for skill {skill_name}: {result.error}")
                return result.output
            raise ValueError(f"SkillRuntime: Skill '{skill_name}' not found in registry")

        # 2. Check if a python-backed tool exists in dispatcher for this skill
        # Maps skill name to dispatcher tool action name if they differ
        skill_to_tool_map = {
            "rag_retrieval": "qdrant_search",
            "apollo_search": "lead_discovery",
            "hunter_verification": "enrichment",
            "opportunity_scoring": "opportunity",
            "signal_detection": "signal_intelligence",
            "email_generation": "email_writer",
            "followup_generation": "followup",
            "reply_classification": "reply_monitor",
            "campaign_analysis": "analytics",
            "web_scraping": "web_scraping",
        }
        
        tool_name = skill_to_tool_map.get(skill.name, skill.name)
        
        if self.dispatcher.has_tool(tool_name):
            logger.info(f"SkillRuntime: Delegating skill '{skill.name}' to tool '{tool_name}'")
            # Execute tool via ToolDispatcher
            result = await self.dispatcher.execute(
                tool_name=tool_name,
                inputs=inputs,
                context=context.to_dict(),
                workflow_run_id=workflow_run_id
            )
            if not result.success:
                raise RuntimeError(f"Tool execution failed for skill {skill_name}: {result.error}")
            return result.output

        # 3. Dynamic LLM-driven Skill Execution fallback
        logger.info(f"SkillRuntime: Executing skill '{skill.name}' dynamically via LLM interface")
        return await self._execute_dynamic_skill(skill, inputs, context, workflow_run_id)

    async def _execute_dynamic_skill(
        self,
        skill: SkillConfig,
        inputs: Dict[str, Any],
        context: ExecutionContext,
        workflow_run_id: str
    ) -> Dict[str, Any]:
        steps_text = "\n".join(f"- {step}" for step in skill.execution_steps)
        rules_text = "\n".join(f"- {rule}" for rule in skill.validation_rules)
        
        system_prompt = f"""You are executing the Skill: {skill.name}.
Purpose: {skill.purpose}

Execution Steps:
{steps_text}

Validation Rules:
{rules_text}

Return your output strictly as a JSON object matching this structure:
{json.dumps(skill.outputs)}
"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Inputs: {json.dumps(inputs)}\nContext: {json.dumps(context.variables)}"}
        ]
        
        response = await self.llm_interface.generate_completion(
            task_type="PLANNING",  # Default planning task type
            messages=messages,
            user_id=context.user.get("id", "system"),
            temperature=0.3,
            workflow_run_id=workflow_run_id
        )
        
        content = response.get("content", "")
        try:
            return self._extract_json(content)
        except Exception as e:
            logger.warning(f"SkillRuntime: Could not parse dynamic skill JSON for '{skill.name}': {e}")
            return {"raw_output": content}

    def _extract_json(self, text: str) -> dict:
        """Extract and parse the first JSON object from a string with repairs."""
        # Simple JSON extract
        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            candidate = text[first_brace : last_brace + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass
        
        # Check markdown blocks
        json_match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1).strip())
            except Exception:
                pass
                
        raise ValueError("No valid JSON found in LLM response.")
