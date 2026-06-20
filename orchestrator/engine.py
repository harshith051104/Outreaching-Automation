"""
Metadata-Driven Agent Orchestrator

A configuration-driven orchestrator that loads agents, skills, workflows,
tools, and memory from declarative files. Supports dynamic agent addition
without code changes.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional
from pathlib import Path
import yaml
import json
import re
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)


class AgentConfig:
    """Parsed agent configuration from markdown file."""

    def __init__(self, name: str, file_path: Path, frontmatter: Dict, content: str):
        self.name = name
        self.file_path = file_path
        self.role = frontmatter.get("role", "")
        self.purpose = frontmatter.get("purpose", "")
        self.version = frontmatter.get("version", "1.0.0")
        self.inputs = frontmatter.get("inputs", {})
        self.outputs = frontmatter.get("outputs", {})
        self.tools = frontmatter.get("tools_allowed", [])
        self.memory_access = frontmatter.get("memory_access", {})
        self.decision_rules = frontmatter.get("decision_rules", [])
        self.constraints = frontmatter.get("constraints", [])
        self.success_criteria = frontmatter.get("success_criteria", [])
        self.escalation_rules = frontmatter.get("escalation_rules", [])
        self.content = content

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "role": self.role,
            "purpose": self.purpose,
            "tools": self.tools,
            "inputs": self.inputs,
            "outputs": self.outputs,
        }


class SkillConfig:
    """Parsed skill configuration from markdown file."""

    def __init__(self, name: str, file_path: Path, content: str):
        self.name = name
        self.file_path = file_path
        self.content = content
        self.purpose = self._extract_section("## Purpose")
        self.inputs = self._extract_schema("## Inputs")
        self.outputs = self._extract_schema("## Outputs")
        self.execution_steps = self._extract_list("## Execution Steps")
        self.validation_rules = self._extract_list("## Validation Rules")
        self.failure_handling = self._extract_section("## Failure Handling")

    def _extract_section(self, heading: str) -> str:
        pattern = f"{heading}\\n(.*?)(?=\\n## |\\Z)"
        match = re.search(pattern, self.content, re.DOTALL)
        return match.group(1).strip() if match else ""

    def _extract_schema(self, heading: str) -> Dict:
        pattern = f"{heading}\\n(.*?)(?=\\n## |\\Z)"
        match = re.search(pattern, self.content, re.DOTALL)
        if not match:
            return {}
        try:
            return yaml.safe_load(match.group(1)) or {}
        except:
            return {}

    def _extract_list(self, heading: str) -> List[str]:
        pattern = f"{heading}\\n(.*?)(?=\\n## |\\Z)"
        match = re.search(pattern, self.content, re.DOTALL)
        if not match:
            return []
        items = re.findall(r"^\s*-\s+(.+)$", match.group(1), re.MULTILINE)
        return items


class WorkflowConfig:
    """Parsed workflow configuration from YAML file."""

    def __init__(self, name: str, file_path: Path, data: Dict):
        self.name = name
        self.file_path = file_path
        self.version = data.get("version", "1.0.0")
        self.description = data.get("description", "")
        self.agents = data.get("agents", [])
        self.skills = data.get("skills", [])
        self.steps = data.get("steps", [])
        self.outputs = data.get("outputs", {})
        self.error_handling = data.get("error_handling", [])

    def get_step(self, step_id: str) -> Optional[Dict]:
        for step in self.steps:
            if step.get("id") == step_id:
                return step
        return None

    def get_steps_ordered(self) -> List[Dict]:
        return self.steps


class ToolConfig:
    """Parsed tool configuration from tools.yaml."""

    def __init__(self, name: str, config: Dict):
        self.name = name
        self.purpose = config.get("purpose", "")
        self.category = config.get("category", "")
        self.api = config.get("api", "")
        self.authentication = config.get("authentication", "")
        self.rate_limit = config.get("rate_limit", {})
        self.input_schema = config.get("input_schema", {})
        self.output_schema = config.get("output_schema", {})
        self.retry_strategy = config.get("retry_strategy", {})

    def validate_input(self, data: Dict) -> tuple[bool, str]:
        required = self.input_schema.get("required", [])
        for field in required:
            if field not in data:
                return False, f"Missing required field: {field}"
        return True, ""


class ActionRegistry:
    """Registry for mapping workflow actions to python implementations."""
    def __init__(self):
        self._actions: Dict[str, callable] = {}

    def register(self, name: str, func: callable, allow_override: bool = False) -> None:
        if name in self._actions and not allow_override:
            raise ValueError(f"Duplicate action detected: {name}")
        self._actions[name] = func
        logger.info(f"Registered action: {name}")

    def get(self, name: str) -> Optional[callable]:
        return self._actions.get(name)

    def contains(self, name: str) -> bool:
        return name in self._actions


class SkillExecutor:
    """Executor for dynamic or python-backed skills loaded from skills markdown."""
    def __init__(self, orchestrator: "Orchestrator"):
        self.orchestrator = orchestrator

    async def execute(self, skill_name: str, inputs: Dict[str, Any], context: Dict[str, Any]) -> Any:
        skill = self.orchestrator.skills.get(skill_name)
        if not skill:
            clean_name = skill_name.lower().replace("_skill", "")
            skill = self.orchestrator.skills.get(clean_name) or self.orchestrator.skills.get(f"{clean_name}_skill")
        if not skill:
            raise ValueError(f"Skill not found: {skill_name}")

        resolved_inputs = self.orchestrator._resolve_template(inputs, context)
        
        # Check for python action counterpart
        skill_to_action_map = {
            "rag_retrieval": "rag_search",
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
        
        action_name = skill_to_action_map.get(skill.name, skill.name)
        if self.orchestrator.action_registry.contains(action_name):
            logger.info(f"SkillExecutor: Executing skill '{skill_name}' via action '{action_name}'")
            return await self.orchestrator.action_registry.get(action_name)(resolved_inputs, context)
            
        logger.info(f"SkillExecutor: Executing skill '{skill_name}' dynamically via LLM Completion")
        return await self._run_dynamic_skill(skill, resolved_inputs, context)

    async def _run_dynamic_skill(self, skill: SkillConfig, inputs: Dict, context: Dict) -> Dict:
        system_prompt = f"""You are executing the Skill: {skill.name}.
Purpose: {skill.purpose}

Execution Steps:
{chr(10).join(f'- {step}' for step in skill.execution_steps)}

Validation Rules:
{chr(10).join(f'- {rule}' for rule in skill.validation_rules)}

Inputs: {json.dumps(inputs)}

Return your output strictly as a JSON object matching this structure:
{json.dumps(skill.outputs)}
"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Context: {json.dumps(context)}"}
        ]
        inference_result = await self.orchestrator._llm_inference({"messages": messages}, {})
        content = inference_result.get("content", "")
        try:
            return self.orchestrator._extract_json(content)
        except Exception as e:
            logger.warning(f"Could not parse dynamic skill output: {e}")
            return {"raw_output": content}


class WorkflowExecutor:
    """Handles execution of a workflow's steps with chaining, context, retry, and error handling."""
    def __init__(self, orchestrator: "Orchestrator"):
        self.orchestrator = orchestrator

    async def execute(
        self,
        workflow: WorkflowConfig,
        inputs: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        ctx = context or {}
        ctx["inputs"] = inputs
        ctx["_step_outputs"] = {}
        ctx["steps"] = {}
        
        logger.info(f"WorkflowExecutor: Executing workflow '{workflow.name}'")
        
        for step in workflow.get_steps_ordered():
            step_id = step.get("id", "")
            retry_count = step.get("retry_count", 0)
            
            # Find retry count from error handling config if any
            for eh in workflow.error_handling:
                if eh.get("step") == step_id:
                    retry_count = max(retry_count, eh.get("retry_count", 0))

            attempt = 0
            success = False
            result = None
            last_err = None
            continue_on_failure = step.get("continue_on_failure", False)
            # Also check error_handling config for log_and_continue
            for eh in workflow.error_handling:
                if eh.get("step") == step_id and eh.get("on_failure") == "log_and_continue":
                    continue_on_failure = True

            while attempt <= retry_count:
                try:
                    result = await self._execute_step(step, ctx)
                    success = True
                    break
                except Exception as e:
                    last_err = e
                    logger.error(f"WorkflowExecutor: Step '{step_id}' failed on attempt {attempt + 1}: {e}")
                    attempt += 1
                    
            if not success:
                logger.error(f"WorkflowExecutor: Step '{step_id}' failed after {retry_count + 1} attempts")
                if continue_on_failure:
                    logger.warning(f"WorkflowExecutor: Step '{step_id}' continuing despite failure (continue_on_failure=True)")
                    result = {"error": str(last_err), "skipped": True}
                else:
                    error_handlers = self.orchestrator._get_error_handlers(workflow, step_id)
                    if error_handlers:
                        for handler in error_handlers:
                            await self.orchestrator._execute_error_handler(handler, ctx, last_err)
                    else:
                        raise last_err

            ctx["_step_outputs"][step_id] = result
            ctx["steps"][step_id] = {"output": result}
            
            output_var = step.get("output_var")
            if output_var:
                ctx[output_var] = result

        return self.orchestrator._resolve_outputs(workflow.outputs, ctx)

    async def _execute_step(self, step: Dict, ctx: Dict) -> Any:
        step_id = step.get("id", "")
        action = step.get("action") or step.get("agent")
        
        if step.get("foreach"):
            items = self.orchestrator._resolve_value(step["foreach"], ctx)
            if not isinstance(items, list):
                items = [items] if items else []
            results = []
            for item in items:
                item_ctx = {**ctx, "item": item, "reply_item": item}
                result = await self._execute_step({**step, "foreach": None}, item_ctx)
                results.append(result)
            return results

        if step.get("parallel"):
            tasks = []
            for sub_step in step.get("steps", []):
                tasks.append(self._execute_step(sub_step, ctx))
            return await asyncio.gather(*tasks)

        input_template = step.get("input", {})
        resolved_inputs = self.orchestrator._resolve_template(input_template, ctx)

        if step.get("agent"):
            agent_name = step["agent"]
            return await self.orchestrator._execute_agent(agent_name, resolved_inputs, ctx)

        if not action:
            raise ValueError(f"Step '{step_id}' has neither agent nor action.")

        # Check if action is a skill
        clean_action = action.lower().replace("_skill", "")
        if action in self.orchestrator.skills or clean_action in self.orchestrator.skills:
            return await self.orchestrator.skill_executor.execute(action, resolved_inputs, ctx)

        # Check ActionRegistry
        if self.orchestrator.action_registry.contains(action):
            action_func = self.orchestrator.action_registry.get(action)
            return await action_func(resolved_inputs, ctx)
            
        # Built-ins
        if action == "conditional":
            return await self.orchestrator._conditional_action(resolved_inputs, ctx)
        elif action == "pass_through":
            return self.orchestrator._resolve_value(resolved_inputs.get("data"), ctx)
        elif action == "validate":
            return {"valid": True}
        else:
            raise ValueError(f"Unknown action or skill: {action}")


class Orchestrator:
    """
    Metadata-driven agent orchestrator.

    Loads all configuration from declarative files and executes workflows
    by coordinating agents, skills, and tools.
    """

    def __init__(self, base_path: Optional[Path] = None):
        self.base_path = base_path or Path(__file__).parent.parent
        self.agents: Dict[str, AgentConfig] = {}
        self.skills: Dict[str, SkillConfig] = {}
        self.workflows: Dict[str, WorkflowConfig] = {}
        self.tools: Dict[str, ToolConfig] = {}
        self.memory_registry: Dict[str, Any] = {}
        self.tool_instances: Dict[str, Any] = {}
        self.action_registry = ActionRegistry()
        self.skill_executor = SkillExecutor(self)
        self.workflow_executor = WorkflowExecutor(self)
        self._initialized = False
        self._init_lock = asyncio.Lock()
        self._groq_client = None
        self._groq_sync_client = None

    async def initialize(self) -> None:
        """Load all configurations from disk and validate them."""
        async with self._init_lock:
            if self._initialized:
                return

            logger.info("Initializing orchestrator...")

            await self._load_agents()
            await self._load_skills()
            await self._load_workflows()
            await self._load_tools()
            await self._load_memory_registry()
            await self._initialize_tool_instances()
            await self._initialize_action_registry()
            await self.validate_workflows()

            self._initialized = True
            logger.info(
                f"Orchestrator initialized: {len(self.agents)} agents, "
                f"{len(self.skills)} skills, {len(self.workflows)} workflows, "
                f"{len(self.tools)} tools"
            )

    async def _load_agents(self) -> None:
        """Load all agent markdown files."""
        agents_dir = self.base_path / "agents"
        if not agents_dir.exists():
            logger.warning(f"Agents directory not found: {agents_dir}")
            return

        for md_file in agents_dir.glob("*.md"):
            try:
                content = md_file.read_text(encoding="utf-8")
                frontmatter, body = self._parse_yaml_frontmatter(content)
                agent_name = md_file.stem
                self.agents[agent_name] = AgentConfig(agent_name, md_file, frontmatter, body)
                logger.debug(f"Loaded agent: {agent_name}")
            except Exception as e:
                logger.error(f"Failed to load agent {md_file}: {e}")

    async def _load_skills(self) -> None:
        """Load all skill markdown files."""
        skills_dir = self.base_path / "skills"
        if not skills_dir.exists():
            logger.warning(f"Skills directory not found: {skills_dir}")
            return

        for md_file in skills_dir.glob("*.md"):
            try:
                content = md_file.read_text(encoding="utf-8")
                skill_name = md_file.stem
                self.skills[skill_name] = SkillConfig(skill_name, md_file, content)
                logger.debug(f"Loaded skill: {skill_name}")
            except Exception as e:
                logger.error(f"Failed to load skill {md_file}: {e}")

    async def _load_workflows(self) -> None:
        """Load all workflow YAML files."""
        workflows_dir = self.base_path / "workflows"
        if not workflows_dir.exists():
            logger.warning(f"Workflows directory not found: {workflows_dir}")
            return

        for yaml_file in workflows_dir.glob("*.yaml"):
            try:
                data = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
                workflow_name = data.get("name", yaml_file.stem)
                self.workflows[workflow_name] = WorkflowConfig(workflow_name, yaml_file, data)
                logger.debug(f"Loaded workflow: {workflow_name}")
            except Exception as e:
                logger.error(f"Failed to load workflow {yaml_file}: {e}")

    async def _load_tools(self) -> None:
        """Load tools registry."""
        tools_file = self.base_path / "tools" / "tools.yaml"
        if not tools_file.exists():
            logger.warning(f"Tools registry not found: {tools_file}")
            return

        try:
            data = yaml.safe_load(tools_file.read_text(encoding="utf-8"))
            for tool_name, tool_config in data.get("tools", {}).items():
                self.tools[tool_name] = ToolConfig(tool_name, tool_config)
            logger.debug(f"Loaded {len(self.tools)} tools")
        except Exception as e:
            logger.error(f"Failed to load tools registry: {e}")

    async def _load_memory_registry(self) -> None:
        """Load memory registry."""
        memory_file = self.base_path / "memory" / "memory_registry.yaml"
        if not memory_file.exists():
            logger.warning(f"Memory registry not found: {memory_file}")
            return

        try:
            self.memory_registry = yaml.safe_load(memory_file.read_text(encoding="utf-8"))
            logger.debug("Loaded memory registry")
        except Exception as e:
            logger.error(f"Failed to load memory registry: {e}")

    async def _initialize_tool_instances(self) -> None:
        """Initialize tool instances for execution."""
        self.tool_instances = {
            "mongodb_query": self._mongodb_query,
            "mongodb_insert": self._mongodb_insert,
            "mongodb_update": self._mongodb_update,
            "mongodb_upsert": self._mongodb_upsert,
            "qdrant_search": self._qdrant_search,
            "qdrant_upsert": self._qdrant_upsert,
            "llm_inference": self._llm_inference,
            "spam_check": self._spam_check,
            "gmail_send": self._gmail_send,
            "gmail_check_replies": self._gmail_check_replies,
            "websocket_broadcast": self._websocket_broadcast,
        }

    def _parse_yaml_frontmatter(self, content: str) -> tuple[Dict, str]:
        """Parse YAML frontmatter from markdown content."""
        pattern = r"^---\n(.*?)\n---\n(.*)$"
        match = re.match(pattern, content, re.DOTALL)
        if match:
            frontmatter = yaml.safe_load(match.group(1)) or {}
            body = match.group(2)
            return frontmatter, body
        return {}, content

    async def execute_workflow(
        self,
        workflow_name: str,
        inputs: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute a workflow by name with given inputs.

        Args:
            workflow_name: Name of the workflow to execute
            inputs: Input parameters for the workflow
            context: Shared execution context

        Returns:
            Workflow outputs
        """
        if not self._initialized:
            await self.initialize()

        workflow = self.workflows.get(workflow_name)
        if not workflow:
            raise ValueError(f"Workflow not found: {workflow_name}")

        return await self.workflow_executor.execute(workflow, inputs, context)

    async def _execute_agent(self, agent_name: str, input_template: Dict, ctx: Dict) -> Any:
        """Execute an agent with given inputs dynamically using configured handlers or a generic LLM run."""
        agent = self.agents.get(agent_name)
        if not agent:
            clean_name = agent_name.lower().replace("_agent", "")
            agent = self.agents.get(clean_name) or self.agents.get(f"{clean_name}_agent")
            if not agent:
                raise ValueError(f"Agent not found: {agent_name}")

        inputs = self._resolve_template(input_template, ctx)

        method_names = [
            f"_agent_{agent_name}",
            f"_agent_{agent.name}",
            f"_agent_{agent_name.replace('_agent', '')}",
        ]
        
        for method_name in method_names:
            if hasattr(self, method_name):
                method = getattr(self, method_name)
                logger.info(f"Dispatching to custom handler method '{method_name}' for agent '{agent_name}'")
                return await method(inputs)

        logger.info(f"Fallback to dynamic configuration-driven runner for agent '{agent_name}'")
        return await self._run_generic_agent(agent, inputs)

    async def _run_generic_agent(self, agent: AgentConfig, inputs: Dict) -> Dict:
        """Execute an agent dynamically based on its markdown configuration and frontmatter."""
        constraints_text = "\n".join(f"- {c}" for c in agent.constraints[:10]) if isinstance(agent.constraints, list) and agent.constraints else "None"
        rules_text = "\n".join(f"- {r}" for r in agent.decision_rules[:10]) if isinstance(agent.decision_rules, list) and agent.decision_rules else "None"
        criteria_text = "\n".join(f"- {c}" for c in agent.success_criteria[:10]) if isinstance(agent.success_criteria, list) and agent.success_criteria else "None"

        system_prompt = f"""You are the {agent.role}.
Purpose: {agent.purpose}

Instructions:
{agent.content}

Constraints:
{constraints_text}

Decision Rules:
{rules_text}

Success Criteria:
{criteria_text}

Return your output strictly as a JSON object matching this structure:
{json.dumps(agent.outputs)}
"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Inputs: {json.dumps(inputs)}"}
        ]
        
        inference_result = await self._llm_inference({"messages": messages}, {})
        content = inference_result.get("content", "")
        
        try:
            return self._extract_json(content)
        except Exception as e:
            logger.warning(f"Could not parse dynamic agent output as JSON: {e}")
            return {"raw_output": content}

    def _extract_json(self, text: str) -> dict:
        """Extract and parse the first JSON object found in a text string."""
        # 1. Try to load the entire text directly
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 2. Try to extract JSON from markdown code blocks
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # 3. Try to locate the outermost matching braces (brace depth tracking)
        brace_start = text.find("{")
        if brace_start != -1:
            depth = 0
            for i in range(brace_start, len(text)):
                if text[i] == "{":
                    depth += 1
                elif text[i] == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(text[brace_start : i + 1])
                        except json.JSONDecodeError:
                            pass

        # 4. Fallback: search for a greedy match between first '{' and last '}'
        try:
            first_brace = text.find("{")
            last_brace = text.rfind("}")
            if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                return json.loads(text[first_brace : last_brace + 1])
        except json.JSONDecodeError:
            pass

        raise ValueError("No valid JSON found in text.")

    async def _agent_tracking(self, inputs: Dict) -> Dict:
        """Execute tracking agent by calling the generic agent runner."""
        agent = self.agents.get("analytics_agent")
        if not agent:
            raise ValueError("analytics_agent configuration not found for tracking")
        return await self._run_generic_agent(agent, inputs)

    async def _agent_tracking_agent(self, inputs: Dict) -> Dict:
        """Execute tracking agent by calling the generic agent runner."""
        return await self._agent_tracking(inputs)

    async def _agent_lead_discovery(self, inputs: Dict) -> Dict:
        """Execute lead discovery agent."""
        from app.services.apollo_service import ApolloService
        from app.services.tavily_service import TavilyService

        apollo = ApolloService()
        tavily = TavilyService()

        try:
            raw_leads = await apollo.search_leads(
                job_titles=inputs.get("job_titles", []),
                locations=inputs.get("locations", []),
                industry=inputs.get("industry"),
                limit=inputs.get("limit", 10),
            )
            if raw_leads:
                return {"leads": raw_leads, "source": "apollo"}

            tavily_results = await tavily.search(
                query=" ".join(inputs.get("job_titles", [])),
                max_results=inputs.get("limit", 10),
            )
            leads = [{"name": r.get("title", ""), "email": "", "source": "tavily"} for r in tavily_results]
            return {"leads": leads, "source": "tavily"}
        except Exception as e:
            logger.error(f"Lead discovery failed: {e}")
            return {"leads": [], "source": "error", "error": str(e)}

    async def _agent_signal_intelligence(self, inputs: Dict) -> Dict:
        """Execute signal intelligence agent."""
        from app.services.signal_service import SignalService

        signal_service = SignalService()
        signals = await signal_service.gather_and_store_signals(
            lead_id=inputs.get("lead_id", ""),
            company_name=inputs.get("company_name", ""),
            website_url=inputs.get("website_url"),
        )
        return {"signals": signals}

    async def _agent_research(self, inputs: Dict) -> Dict:
        """Execute research agent."""
        from app.agents.research_agent import research_lead

        result = await asyncio.to_thread(research_lead, inputs)
        return result

    async def _agent_personalization(self, inputs: Dict) -> Dict:
        """Execute personalization agent."""
        from app.agents.personalization_agent import personalize_for_lead

        result = await asyncio.to_thread(
            personalize_for_lead,
            inputs.get("lead_data", inputs),
            inputs.get("research_data", {}),
        )
        return result

    async def _agent_email_writer(self, inputs: Dict) -> Dict:
        """Execute email writer agent."""
        from app.agents.outreach_writer_agent import write_outreach_email

        result = await asyncio.to_thread(
            write_outreach_email,
            inputs.get("lead_data", {}),
            inputs.get("personalization_data", {}),
            inputs.get("tone", "professional"),
        )
        return result

    async def _agent_followup(self, inputs: Dict) -> Dict:
        """Execute followup agent."""
        from app.agents.followup_agent import generate_followup
        from app.config.mongodb_config import get_database

        lead_data = dict(inputs.get("lead_data", {}))
        if "sender_name" not in lead_data:
            campaign_id = inputs.get("campaign_id")
            if campaign_id:
                try:
                    db = await get_database()
                    campaign = await db.campaigns.find_one({"id": campaign_id})
                    if campaign:
                        user = await db.users.find_one({"id": campaign["user_id"]})
                        user_name = user.get("name", "") if user else ""
                        
                        gmail_account_id = campaign.get("gmail_account_id", "")
                        if gmail_account_id:
                            gmail_account = await db.gmail_accounts.find_one({"id": gmail_account_id})
                            sender_name = gmail_account.get("name", user_name) if gmail_account else user_name
                        else:
                            sender_name = user_name
                        lead_data["sender_name"] = sender_name
                except Exception as exc:
                    logger.warning("Failed to resolve sender_name in _agent_followup: %s", exc)

        result = await asyncio.to_thread(
            generate_followup,
            inputs.get("original_email", {}),
            lead_data,
            inputs.get("sequence_number", 1),
            inputs.get("engagement_data", {}),
        )
        return result

    async def _agent_reply_monitor(self, inputs: Dict) -> Dict:
        """Execute reply classification agent."""
        from app.agents.reply_classification_agent import classify_reply

        result = await asyncio.to_thread(
            classify_reply,
            inputs.get("reply_text", ""),
            inputs.get("original_email", ""),
            inputs.get("lead_context", {}),
        )
        return result

    async def _agent_analytics(self, inputs: Dict) -> Dict:
        """Execute analytics agent."""
        from app.agents.analytics_agent import generate_campaign_insights

        result = await asyncio.to_thread(
            generate_campaign_insights,
            inputs.get("campaign_data", {}),
            inputs.get("analytics_data", {}),
        )
        return result

    async def _agent_enrichment(self, inputs: Dict) -> Dict:
        """Execute enrichment agent."""
        from app.services.hunter_enrichment_service import HunterEnrichmentService

        hunter = HunterEnrichmentService()
        result = await hunter.verify_email(inputs.get("email", ""))
        return result

    async def _agent_opportunity(self, inputs: Dict) -> Dict:
        """Execute opportunity intelligence agent."""
        from app.services.signal_service import SignalService

        signal_service = SignalService()
        result = await signal_service.evaluate_opportunity(inputs.get("lead_id", ""))
        return result

    async def _mongodb_query(self, input_data: Dict, ctx: Dict) -> Any:
        """Execute MongoDB query."""
        from app.config.mongodb_config import get_database

        db = await get_database()
        collection = db[input_data.get("collection", "")]
        query = self._resolve_value(input_data.get("query", {}), ctx)
        docs = await collection.find(query).to_list(length=input_data.get("limit", 50))
        return docs

    async def _mongodb_insert(self, input_data: Dict, ctx: Dict) -> Any:
        """Execute MongoDB insert (handles both single document and list of documents)."""
        from app.config.mongodb_config import get_database
        from app.utils.id_generator import generate_id

        db = await get_database()
        collection = db[input_data.get("collection", "")]

        if "documents" in input_data:
            docs = self._resolve_value(input_data["documents"], ctx)
            if not isinstance(docs, list):
                docs = [docs] if docs else []
            for doc in docs:
                if isinstance(doc, dict):
                    if "id" not in doc:
                        doc["id"] = generate_id()
                    doc.pop("_id", None)
            if docs:
                result = await collection.insert_many(docs)
                return {"ids": [str(x) for x in result.inserted_ids], "documents": docs, "count": len(docs)}
            return {"ids": [], "documents": [], "count": 0}
        else:
            doc = self._resolve_value(input_data.get("document", {}), ctx)
            if isinstance(doc, dict):
                if "id" not in doc:
                    doc["id"] = generate_id()
                doc.pop("_id", None)
                result = await collection.insert_one(doc)
                return {"id": str(result.inserted_id), "document": doc}
            return {"id": None, "document": {}}

    async def _mongodb_update(self, input_data: Dict, ctx: Dict) -> Any:
        """Execute MongoDB update."""
        from app.config.mongodb_config import get_database

        db = await get_database()
        collection = db[input_data.get("collection", "")]

        query = self._resolve_value(input_data.get("query", {}), ctx)
        if isinstance(query, dict):
            query.pop("_id", None)
        update = self._resolve_value(input_data.get("update", {}), ctx)
        if isinstance(update, dict):
            update.pop("_id", None)
            if not any(k.startswith("$") for k in update.keys()):
                update = {"$set": update}

        result = await collection.update_one(query, update)
        return {"matched_count": result.matched_count, "modified_count": result.modified_count}

    async def _mongodb_upsert(self, input_data: Dict, ctx: Dict) -> Any:
        """Execute MongoDB upsert."""
        from app.config.mongodb_config import get_database

        db = await get_database()
        collection = db[input_data.get("collection", "")]

        query = self._resolve_value(input_data.get("query", {}), ctx)
        if isinstance(query, dict):
            query.pop("_id", None)
        doc = self._resolve_value(input_data.get("doc", {}), ctx)
        if isinstance(doc, dict):
            doc.pop("_id", None)

        result = await collection.update_one(query, {"$set": doc}, upsert=True)
        return {"upserted_id": str(result.upserted_id) if result.upserted_id else None}

    async def _qdrant_search(self, input_data: Dict, ctx: Dict) -> Any:
        """Execute Qdrant vector search."""
        from app.services.qdrant_service import search_similar

        results = await search_similar(
            collection_name=input_data.get("collection", "leads"),
            query=input_data.get("query", ""),
            limit=input_data.get("limit", 3),
        )
        return results

    async def _qdrant_upsert(self, input_data: Dict, ctx: Dict) -> Any:
        """Execute Qdrant upsert (supports singular doc or batch documents)."""
        from app.services.qdrant_service import store_document

        collection = input_data.get("collection", "leads")
        if "documents" in input_data:
            docs = self._resolve_value(input_data["documents"], ctx)
            if not isinstance(docs, list):
                docs = [docs] if docs else []
            for doc in docs:
                if isinstance(doc, dict):
                    doc_id = doc.get("id") or doc.get("_id")
                    if not doc_id:
                        continue
                    text = f"Lead: {doc.get('name')}, Role: {doc.get('role')}, Company: {doc.get('company')}"
                    metadata = {
                        "user_id": doc.get("user_id"),
                        "campaign_id": doc.get("campaign_id"),
                        "lead_quality_score": doc.get("lead_quality_score")
                    }
                    await store_document(
                        collection_name=collection,
                        doc_id=str(doc_id),
                        text=text,
                        metadata=metadata
                    )
            return {"success": True, "count": len(docs)}
        else:
            doc_id = input_data.get("doc_id", "")
            text = input_data.get("text", "")
            metadata = input_data.get("metadata", {})
            await store_document(
                collection_name=collection,
                doc_id=doc_id,
                text=text,
                metadata=metadata,
            )
            return {"success": True}

    async def _llm_inference(self, input_data: Dict, ctx: Dict) -> Any:
        """Execute LLM inference without blocking the event loop."""
        from app.config.settings import settings

        messages = input_data.get("messages", [])
        model = input_data.get("model", settings.GROQ_MODEL or "llama-3.3-70b-versatile")
        temperature = input_data.get("temperature", 0.3)
        max_tokens = input_data.get("max_tokens", 2000)

        try:
            # Try AsyncGroq first (groq >= 0.9.0)
            from groq import AsyncGroq
            if not self._groq_client:
                self._groq_client = AsyncGroq(api_key=settings.GROQ_API_KEY)
            response = await self._groq_client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return {"content": response.choices[0].message.content}
        except ImportError:
            # Fallback for older groq versions: run sync client in a thread
            from groq import Groq
            if not self._groq_sync_client:
                self._groq_sync_client = Groq(api_key=settings.GROQ_API_KEY)

            def _sync_call():
                return self._groq_sync_client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )

            response = await asyncio.to_thread(_sync_call)
            return {"content": response.choices[0].message.content}

    async def _spam_check(self, input_data: Dict, ctx: Dict) -> Any:
        """Execute spam analysis."""
        from app.agents.tools.email_tool import EmailAnalysisTool

        tool = EmailAnalysisTool()
        result = tool._run(
            email_content=input_data.get("email_content", ""),
            subject=input_data.get("subject", ""),
        )
        return json.loads(result)

    async def _gmail_send(self, input_data: Dict, ctx: Dict) -> Any:
        """Execute Gmail send."""
        from app.services.gmail_service import send_email
        from app.schemas.gmail import SendEmailRequest

        request_data = SendEmailRequest(
            gmail_account_id=input_data.get("gmail_account_id"),
            to_email=input_data.get("to"),
            subject=input_data.get("subject"),
            body=input_data.get("body_html"),
        )

        result = await send_email(
            user_id=ctx.get("user_id", ""),
            data=request_data,
        )
        return result

    async def _gmail_check_replies(self, input_data: Dict, ctx: Dict) -> Any:
        """Execute Gmail reply check."""
        from app.services.gmail_service import check_for_replies

        replies = await check_for_replies(
            input_data.get("gmail_account_id"),
            input_data.get("thread_ids", []),
        )
        return replies

    async def _websocket_broadcast(self, input_data: Dict, ctx: Dict) -> Any:
        """Execute WebSocket broadcast via the connection manager."""
        try:
            from app.websocket.connection_manager import manager
            user_id = input_data.get("user_id")
            event = input_data.get("event", "notification")
            data = input_data.get("data", {})
            payload = {"type": event, "data": data}
            await manager.send_to_user(user_id, payload)
            return {"delivered": True}
        except Exception as exc:
            logger.warning("WebSocket broadcast failed (non-critical): %s", exc)
            return {"delivered": False, "error": str(exc)}

    def _resolve_value(self, value: Any, ctx: Dict) -> Any:
        """Resolve a value that may contain template references."""
        if isinstance(value, str):
            return self._resolve_template_string(value, ctx)
        elif isinstance(value, dict):
            return {k: self._resolve_value(v, ctx) for k, v in value.items()}
        elif isinstance(value, list):
            return [self._resolve_value(v, ctx) for v in value]
        return value

    def _resolve_template_string(self, template: str, ctx: Dict) -> Any:
        """Resolve {{variable.path}} references in template strings, returning raw types when possible."""
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
        """Resolve template references in a data structure."""
        return self._resolve_value(template, ctx)

    def _resolve_outputs(self, outputs: Dict, ctx: Dict) -> Dict:
        """Resolve workflow output references."""
        result = {}
        for key, value in outputs.items():
            result[key] = self._resolve_value(value, ctx)
        return result

    def _get_error_handlers(self, workflow: WorkflowConfig, step_id: str) -> List[Dict]:
        """Get error handlers for a specific step."""
        handlers = []
        for eh in workflow.error_handling:
            if eh.get("step") == step_id:
                handlers.append(eh)
        return handlers

    async def _execute_error_handler(self, handler: Dict, ctx: Dict, error: Exception) -> None:
        """Execute an error handler."""
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
        elif action == "log_error":
            logger.error(f"Workflow error: {error}")

    @property
    def _builtin_actions(self) -> Dict[str, callable]:
        """Built-in action handlers."""
        return {
            "pass_through": lambda inp, ctx: self._resolve_value(inp.get("data"), ctx),
            "conditional": self._conditional_action,
            "validate": lambda inp, ctx: {"valid": True},
            "compute_engagement": self._compute_engagement,
        }

    async def _conditional_action(self, input_data: Dict, ctx: Dict) -> Any:
        """Execute conditional branch."""
        condition = input_data.get("condition", "")
        if self._evaluate_condition(condition, ctx):
            return await self.workflow_executor._execute_step({"action": input_data.get("true_branch")}, ctx)
        elif "false_branch" in input_data:
            return await self.workflow_executor._execute_step({"action": input_data.get("false_branch")}, ctx)
        return None

    def _evaluate_condition(self, condition: str, ctx: Dict) -> bool:
        """Evaluate a simple condition string."""
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

    async def _compute_engagement(self, input_data: Dict, ctx: Dict) -> Dict:
        """Compute engagement signals for a lead."""
        from app.config.mongodb_config import get_database

        db = await get_database()
        lead_id = input_data.get("lead_id")
        campaign_id = input_data.get("campaign_id")

        opens = await db.tracking_events.count_documents({
            "lead_id": lead_id,
            "campaign_id": campaign_id,
            "event_type": "open",
        })
        clicks = await db.tracking_events.count_documents({
            "lead_id": lead_id,
            "campaign_id": campaign_id,
            "event_type": "click",
        })

        return {
            "opened": opens > 0,
            "clicked": clicks > 0,
            "open_count": opens,
            "click_count": clicks,
        }

    async def _initialize_action_registry(self) -> None:
        """Register all workflow actions in the ActionRegistry."""
        if hasattr(self, '_action_registry_initialized') and self._action_registry_initialized:
            return

        # Core Database Actions
        self.action_registry.register("mongodb_query", self._mongodb_query)
        self.action_registry.register("mongodb_query_one", self._mongodb_query_one)
        self.action_registry.register("mongodb_insert", self._mongodb_insert)
        self.action_registry.register("mongodb_update", self._mongodb_update)
        self.action_registry.register("mongodb_upsert", self._mongodb_upsert)

        # Search & Vector Actions
        self.action_registry.register("qdrant_search", self._qdrant_search)
        self.action_registry.register("qdrant_upsert", self._qdrant_upsert)
        self.action_registry.register("rag_search", self._qdrant_search)  # Alias

        # LLM & AI Actions
        self.action_registry.register("llm_inference", self._llm_inference)
        self.action_registry.register("spam_check", self._spam_check)
        self.action_registry.register("tavily_search", self._tavily_search)
        self.action_registry.register("transform_tavily_to_leads", self._transform_tavily_to_leads)

        # Email & Gmail Actions
        self.action_registry.register("gmail_send", self._gmail_send)
        self.action_registry.register("gmail_check_replies", self._gmail_check_replies)

        # Real-time Actions
        self.action_registry.register("websocket_broadcast", self._websocket_broadcast)

        # Analytics & Metrics Actions
        self.action_registry.register("compute_engagement", self._compute_engagement)
        self.action_registry.register("compute_campaign_metrics", self._compute_campaign_metrics)
        self.action_registry.register("compute_campaign_metrics_batch", self._compute_campaign_metrics_batch)
        self.action_registry.register("compute_basic_insights", self._compute_basic_insights)
        self.action_registry.register("deduplicate", self._deduplicate)
        self.action_registry.register("calculate_quality_score", self._calculate_quality_score)

        # Workflow & Sequence Actions
        self.action_registry.register("create_followup_tasks", self._create_followup_tasks)
        self.action_registry.register("find_active_campaigns", self._find_active_campaigns)
        self.action_registry.register("select_approach", self._select_approach)
        self.action_registry.register("calculate_delay", self._calculate_delay)
        self.action_registry.register("generate_template_followup", self._generate_template_followup)
        self.action_registry.register("resolve_or_select_gmail", self._resolve_or_select_gmail)
        self.action_registry.register("build_campaign_document", self._build_campaign_document)
        self.action_registry.register("create_default_steps", self._create_default_steps)

        # LinkedIn Outreach Actions
        self.action_registry.register("linkedin_profile_scrape", self._linkedin_profile_scrape)
        self.action_registry.register("linkedin_send_connection", self._linkedin_send_connection)
        self.action_registry.register("linkedin_send_message", self._linkedin_send_message)
        self.action_registry.register("linkedin_monitor_connections", self._linkedin_monitor_connections)
        self.action_registry.register("linkedin_update_relationship", self._linkedin_update_relationship)
        self.action_registry.register("linkedin_check_daily_limit", self._linkedin_check_daily_limit)
        self.action_registry.register("linkedin_increment_daily_count", self._linkedin_increment_daily_count)
        self.action_registry.register("linkedin_validate_session", self._linkedin_validate_session)

        self._action_registry_initialized = True

    async def validate_workflows(self) -> None:
        """Validate all workflows, agents, skills, and actions. Raise ValueError on failure."""
        logger.info("Validating workflows, agents, skills, and actions...")
        for name, workflow in self.workflows.items():
            for agent_name in workflow.agents:
                clean_name = agent_name.lower().replace("_agent", "")
                if not (agent_name in self.agents or clean_name in self.agents or f"{clean_name}_agent" in self.agents):
                    raise ValueError(f"Workflow '{name}' references unknown agent '{agent_name}'")

            for skill_name in workflow.skills:
                clean_skill = skill_name.lower().replace("_skill", "")
                if not (skill_name in self.skills or clean_skill in self.skills or f"{clean_skill}_skill" in self.skills):
                    raise ValueError(f"Workflow '{name}' references unknown skill '{skill_name}'")

            for step in workflow.steps:
                step_id = step.get("id", "unknown")
                agent = step.get("agent")
                action = step.get("action")

                if agent:
                    clean_agent = agent.lower().replace("_agent", "")
                    if not (agent in self.agents or clean_agent in self.agents or f"{clean_agent}_agent" in self.agents):
                        raise ValueError(f"Workflow '{name}' step '{step_id}' references unknown agent '{agent}'")

                if action:
                    if action not in ["conditional", "pass_through", "validate"] and not self.action_registry.contains(action):
                        clean_action = action.lower().replace("_skill", "")
                        if not (action in self.skills or clean_action in self.skills or f"{clean_action}_skill" in self.skills):
                            raise ValueError(f"Workflow '{name}' step '{step_id}' references unknown action or skill '{action}'")

    async def _mongodb_query_one(self, input_data: Dict, ctx: Dict) -> Any:
        """Execute MongoDB query for a single document."""
        from app.config.mongodb_config import get_database
        db = await get_database()
        collection = db[input_data.get("collection", "")]
        query = self._resolve_value(input_data.get("query", {}), ctx)
        if isinstance(query, dict):
            query.pop("_id", None)
        doc = await collection.find_one(query)
        if doc:
            doc.pop("_id", None)
        return doc or {}

    async def _create_followup_tasks(self, input_data: Dict, ctx: Dict) -> Dict:
        """Create followup tasks for a lead."""
        from app.services.followup_service import create_followup
        campaign_id = input_data.get("campaign_id")
        lead_id = input_data.get("lead_id")
        email_id = input_data.get("email_id")
        
        try:
            followup_stages = int(input_data.get("followup_stages") or 3)
        except:
            followup_stages = 3
            
        try:
            followup_delay_days = int(input_data.get("followup_delay_days") or 3)
        except:
            followup_delay_days = 3
            
        user_id = ctx.get("user_id", "system")
        created_tasks = []
        base_time = datetime.now(timezone.utc)
        
        for stage in range(1, followup_stages + 1):
            scheduled_at = base_time + timedelta(days=followup_delay_days * stage)
            task = await create_followup(
                email_id=email_id,
                campaign_id=campaign_id,
                lead_id=lead_id,
                user_id=user_id,
                sequence_number=stage,
                scheduled_at=scheduled_at
            )
            created_tasks.append(task)
            
        return {"tasks": created_tasks, "count": len(created_tasks)}

    async def _find_active_campaigns(self, input_data: Dict, ctx: Dict) -> Dict:
        """Find active campaigns."""
        from app.config.mongodb_config import get_database
        db = await get_database()
        query = input_data.get("query") or {"status": "active"}
        limit = input_data.get("limit", 50)
        
        cursor = db.campaigns.find(query).limit(limit)
        campaigns = await cursor.to_list(length=limit)
        for camp in campaigns:
            camp.pop("_id", None)
            
        return {"active_campaigns": campaigns, "count": len(campaigns)}

    async def _select_approach(self, input_data: Dict, ctx: Dict) -> str:
        """Select follow-up approach based on sequence number."""
        try:
            seq = int(input_data.get("sequence_number") or 1)
        except:
            seq = 1
            
        if seq == 1:
            return "value-add"
        elif seq == 2:
            return "social-proof"
        elif seq == 3:
            return "urgency"
        else:
            return "breakup"

    async def _calculate_delay(self, input_data: Dict, ctx: Dict) -> int:
        """Calculate follow-up delay in hours."""
        try:
            seq = int(input_data.get("sequence_number") or 1)
        except:
            seq = 1
            
        if seq == 1:
            return 72
        elif seq == 2:
            return 120
        elif seq == 3:
            return 168
        else:
            return 336

    async def _generate_template_followup(self, input_data: Dict, ctx: Dict) -> Dict:
        """Generate template fallback email."""
        seq = input_data.get("sequence_number", 1)
        original_subject = input_data.get("original_subject", "our conversation")
        lead_name = input_data.get("lead_name", "there")
        
        subject = f"Re: {original_subject}"
        body_html = (
            f"<p>Hi {lead_name},</p>"
            f"<p>I wanted to follow up on my previous email regarding <strong>{original_subject}</strong>.</p>"
            f"<p>I understand you're busy, but I'd love to connect if you have a moment.</p>"
            f"<p>Best regards</p>"
        )
        body_text = (
            f"Hi {lead_name},\n\n"
            f"I wanted to follow up on my previous email regarding {original_subject}.\n\n"
            f"I understand you're busy, but I'd love to connect if you have a moment.\n\n"
            f"Best regards"
        )
        return {
            "subject": subject,
            "body_html": body_html,
            "body_text": body_text,
            "new_value_added": "Template fallback"
        }

    async def _resolve_or_select_gmail(self, input_data: Dict, ctx: Dict) -> Dict:
        """Resolve a requested Gmail account or select a default one."""
        from app.config.mongodb_config import get_database
        db = await get_database()
        requested_id = input_data.get("requested_account_id")
        user_id = input_data.get("user_id")
        
        if requested_id:
            account = await db.gmail_accounts.find_one({"id": requested_id})
            if account:
                return {"id": account["id"], "email": account["email"]}
                
        account = await db.gmail_accounts.find_one({"user_id": user_id})
        if account:
            return {"id": account["id"], "email": account["email"]}
            
        return {"id": requested_id or "mock_gmail_id", "email": "mock@gmail.com"}

    async def _build_campaign_document(self, input_data: Dict, ctx: Dict) -> Dict:
        """Build campaign document structure."""
        from app.utils.id_generator import generate_id
        settings_data = input_data.get("settings") or {}
        if isinstance(settings_data, str):
            try:
                settings_data = json.loads(settings_data)
            except:
                settings_data = {}
                
        return {
            "id": generate_id(),
            "user_id": input_data.get("user_id"),
            "name": input_data.get("name", "").strip(),
            "description": input_data.get("description", ""),
            "gmail_account_id": input_data.get("gmail_account_id", ""),
            "subject_template": input_data.get("subject_template", ""),
            "body_template": input_data.get("body_template", ""),
            "followup_enabled": True,
            "followup_stages": settings_data.get("followup_stages", 3),
            "followup_delay_days": settings_data.get("followup_delay_days", 3),
            "daily_send_limit": settings_data.get("daily_send_limit", 50),
            "status": "draft",
            "total_leads": 0,
            "emails_sent": 0,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "settings": settings_data
        }

    async def _create_default_steps(self, input_data: Dict, ctx: Dict) -> Dict:
        """Create and store default 7-step sequence for a campaign."""
        from app.config.mongodb_config import get_database
        db = await get_database()
        campaign_id = input_data.get("campaign_id")
        body_template = input_data.get("body_template", "")
        subject_template = input_data.get("subject_template", "")

        default_steps = [
            {"step_number": 1, "channel": "linkedin", "delay_days": 0,
             "body_template": "Hi {{first_name}}, I'd like to connect."},
            {"step_number": 2, "channel": "email", "delay_days": 3,
             "subject_template": subject_template or "Quick question",
             "body_template": body_template or "Hi {{first_name}},"},
            {"step_number": 3, "channel": "linkedin", "delay_days": 6,
             "body_template": "Hi {{first_name}}, I sent you a message earlier. Would love to connect."},
            {"step_number": 4, "channel": "email", "delay_days": 10,
             "subject_template": "Re: " + (subject_template or "Quick question"),
             "body_template": "Hi {{first_name}},\n\nJust following up on my previous message. Any thoughts?"},
            {"step_number": 5, "channel": "linkedin", "delay_days": 15,
             "body_template": "Hi {{first_name}}, great post! Just engaged with it."},
            {"step_number": 6, "channel": "email", "delay_days": 20,
             "subject_template": "{{company}} + {{sender_name}}",
             "body_template": "Hi {{first_name}},\n\nI noticed {{company}} has been growing rapidly. We've helped similar companies achieve great results.\n\nWould love to share how we could help.\n\nBest"},
            {"step_number": 7, "channel": "email", "delay_days": 28,
             "subject_template": "One last try",
             "body_template": "Hi {{first_name}},\n\nI hope this finds you well. I'll respect your time and won't reach out again after this.\n\nBest"}
        ]

        legacy_step = {
            "type": "email",
            "delay": 0,
            "delay_unit": "days",
            "variants": [
                {
                    "subject": subject_template,
                    "body": body_template,
                    "v_disabled": False
                }
            ]
        }
        sequence = {"steps": [legacy_step]}

        await db.campaigns.update_one(
            {"id": campaign_id},
            {"$set": {"sequences": [sequence], "sequence_steps": default_steps}}
        )

        return {"steps": default_steps, "count": len(default_steps)}

    async def _compute_campaign_metrics(self, input_data: Dict, ctx: Dict) -> Dict:
        """Compute metrics for a campaign."""
        from app.services.analytics_service import _compute_analytics
        campaign_id = input_data.get("campaign_id")
        return await _compute_analytics(campaign_id)

    async def _compute_campaign_metrics_batch(self, input_data: Dict, ctx: Dict) -> Dict:
        """Compute metrics for a batch of campaigns."""
        from app.services.analytics_service import _compute_analytics
        campaign_ids = input_data.get("campaign_ids") or []
        if isinstance(campaign_ids, str):
            import ast
            try:
                campaign_ids = ast.literal_eval(campaign_ids)
            except:
                campaign_ids = [campaign_ids]
                
        results = {}
        for c_id in campaign_ids:
            results[c_id] = await _compute_analytics(c_id)
        return results

    async def _compute_basic_insights(self, input_data: Dict, ctx: Dict) -> Dict:
        """Compute basic campaign insights."""
        from app.services.analytics_service import generate_campaign_insights
        campaign_id = input_data.get("campaign") or input_data.get("campaign_id")
        if isinstance(campaign_id, dict):
            campaign_id = campaign_id.get("id")
        return await generate_campaign_insights(campaign_id)

    async def _deduplicate(self, input_data: Dict, ctx: Dict) -> Dict:
        """Deduplicate discovered leads against DB and current batch."""
        from app.config.mongodb_config import get_database
        db = await get_database()
        leads = input_data.get("leads") or []
        campaign_id = input_data.get("campaign_id")
        user_id = ctx.get("user_id", "system")
        
        unique_leads = []
        seen_hashes = set()
        
        for lead_dict in leads:
            email = lead_dict.get("email", "").strip().lower()
            linkedin = lead_dict.get("linkedin", "").strip().lower()
            lead_hash = email or linkedin
            if not lead_hash:
                continue
            if lead_hash in seen_hashes:
                continue
            seen_hashes.add(lead_hash)
            
            or_conditions = [{"lead_hash": lead_hash}]
            if email:
                or_conditions.append({"email": email})
            if linkedin:
                or_conditions.append({"linkedin": linkedin})
                
            existing = await db.leads.find_one({
                "campaign_id": campaign_id,
                "user_id": user_id,
                "$or": or_conditions
            })
            if not existing:
                unique_leads.append(lead_dict)
                
        return {"unique_leads": unique_leads}

    async def _calculate_quality_score(self, input_data: Dict, ctx: Dict) -> Dict:
        """Calculate quality scores for a list of leads."""
        leads = input_data.get("leads") or []
        job_titles = input_data.get("job_titles") or []
        if isinstance(job_titles, str):
            job_titles = [job_titles]
            
        scored_leads = []
        for lead in leads:
            completeness = 0.0
            if lead.get("linkedin"): completeness += 10.0
            if lead.get("website"): completeness += 5.0
            if lead.get("company"): completeness += 10.0
            if lead.get("title") or lead.get("role"): completeness += 5.0
            if lead.get("email"): completeness += 10.0
            
            email_score = 30.0
            verification = lead.get("enrichment_data", {}).get("email_verification", {}) or lead.get("verification_result", {})
            if verification:
                email_score = (float(verification.get("score") or 0.0) / 100.0) * 40.0
                
            fit = 10.0
            role = (lead.get("title") or lead.get("role") or "").lower()
            if job_titles and role:
                for jt in job_titles:
                    if jt.lower() in role:
                        fit = 20.0
                        break
                        
            lead_quality = completeness + email_score + fit
            lead_copy = {**lead}
            lead_copy["lead_quality_score"] = lead_quality
            scored_leads.append(lead_copy)
            
        return {"scored_leads": scored_leads}

    async def _tavily_search(self, input_data: Dict, ctx: Dict) -> Dict:
        """Execute Tavily search query."""
        from app.services.tavily_service import TavilyService
        tavily = TavilyService()
        results = await tavily.search(query=input_data.get("query", ""))
        return {"results": results}

    async def _transform_tavily_to_leads(self, input_data: Dict, ctx: Dict) -> Dict:
        """Transform Tavily search results to standard lead formats."""
        results = input_data.get("results") or []
        leads = []
        for r in results:
            title = r.get("title", "")
            url = r.get("url", "")
            leads.append({
                "name": title or "Tavily Lead",
                "email": "unknown@domain.com",
                "company": "Unknown",
                "website": url,
                "title": "Prospect",
                "source": "tavily"
            })
        return {"leads": leads}

    # ── LinkedIn Action Handlers ────────────────────────────────────────────

    async def _linkedin_profile_scrape(self, input_data: Dict, ctx: Dict) -> Dict:
        """Scrape a LinkedIn profile via Playwright."""
        from app.services.linkedin_outreach_service import scrape_profile
        user_id = input_data.get("user_id") or ctx.get("user_id", "")
        linkedin_url = input_data.get("linkedin_url", "")
        return await scrape_profile(linkedin_url, user_id)

    async def _linkedin_send_connection(self, input_data: Dict, ctx: Dict) -> Dict:
        """Send a LinkedIn connection request via Playwright."""
        from app.services.linkedin_outreach_service import send_connection_request
        user_id = input_data.get("user_id") or ctx.get("user_id", "")
        return await send_connection_request(
            input_data.get("linkedin_url", ""),
            input_data.get("connection_note", ""),
            user_id,
        )

    async def _linkedin_send_message(self, input_data: Dict, ctx: Dict) -> Dict:
        """Send a LinkedIn message via Playwright."""
        from app.services.linkedin_outreach_service import send_message
        user_id = input_data.get("user_id") or ctx.get("user_id", "")
        return await send_message(
            input_data.get("linkedin_url", ""),
            input_data.get("message_text", ""),
            user_id,
        )

    async def _linkedin_monitor_connections(self, input_data: Dict, ctx: Dict) -> Dict:
        """Check for accepted connections and new messages."""
        from app.services.linkedin_outreach_service import get_pending_invitations
        user_id = input_data.get("user_id") or ctx.get("user_id", "")
        return await get_pending_invitations(user_id)

    async def _linkedin_update_relationship(self, input_data: Dict, ctx: Dict) -> Dict:
        """Update the relationship stage for a LinkedIn contact."""
        from app.config.mongodb_config import get_database
        from app.utils.id_generator import generate_id

        db = await get_database()
        user_id = input_data.get("user_id") or ctx.get("user_id", "")
        linkedin_url = input_data.get("linkedin_url", "")
        new_stage = input_data.get("new_stage", "")
        lead_id = input_data.get("lead_id")
        now = datetime.now(timezone.utc)

        existing = await db.linkedin_relationships.find_one(
            {"user_id": user_id, "linkedin_url": linkedin_url}
        )
        previous_stage = existing.get("current_stage", "none") if existing else "none"

        first_name = input_data.get("first_name", "")
        last_name = input_data.get("last_name", "")
        contact_name_input = input_data.get("contact_name", "")
        if first_name in ("", "Unknown"):
            first_name = ""
            last_name = ""
            if contact_name_input and contact_name_input not in ("Unknown", "Feed detail update", ""):
                parts = contact_name_input.split(" ", 1)
                first_name = parts[0] or ""
                last_name = parts[1] if len(parts) > 1 else ""
        if not first_name and lead_id:
            lead = await db.leads.find_one({"id": lead_id})
            if lead:
                first_name = lead.get("first_name", "")
                last_name = lead.get("last_name", "")

        if not first_name and linkedin_url and linkedin_url.startswith("http") and contact_name_input != "Unknown":
            try:
                from app.services.linkedin_outreach_service import scrape_profile
                logger.info(f"Scraping LinkedIn profile for name: {linkedin_url}")
                profile = await scrape_profile(linkedin_url, user_id)
                if profile and profile.get("name") and profile["name"] not in ("Unknown", "Feed detail update", ""):
                    name_parts = profile["name"].split(" ", 1)
                    first_name = name_parts[0] or ""
                    last_name = name_parts[1] if len(name_parts) > 1 else ""
                    logger.info(f"Profile scrape succeeded for {linkedin_url}: {first_name} {last_name}")
                else:
                    logger.warning(f"Profile scrape returned no valid name for {linkedin_url}: {profile}")
            except Exception as exc:
                logger.warning(f"Profile scrape failed for {linkedin_url}: {exc}")

        await db.linkedin_relationships.update_one(
            {"user_id": user_id, "linkedin_url": linkedin_url},
            {
                "$set": {
                    "user_id": user_id,
                    "linkedin_url": linkedin_url,
                    "current_stage": new_stage,
                    "lead_id": lead_id,
                    "updated_at": now,
                    "first_name": first_name,
                    "last_name": last_name,
                    "contact_name": contact_name_input if contact_name_input and contact_name_input not in ("Feed detail update", "") else (f"{first_name} {last_name}".strip() or "Unknown"),
                },
                "$push": {
                    "stage_history": {
                        "from_stage": previous_stage,
                        "to_stage": new_stage,
                        "timestamp": now,
                    }
                },
                "$setOnInsert": {
                    "id": generate_id(),
                    "created_at": now,
                },
            },
            upsert=True,
        )

        # Record tracking event in existing system
        await db.tracking_events.insert_one({
            "id": generate_id(),
            "user_id": user_id,
            "event_type": f"linkedin_{new_stage}",
            "linkedin_url": linkedin_url,
            "lead_id": lead_id,
            "channel": "linkedin",
            "timestamp": now,
        })

        # Synchronize with leads collection status if a match is found
        lead = None
        if lead_id:
            lead = await db.leads.find_one({"id": lead_id})
        if not lead and linkedin_url:
            lead = await db.leads.find_one({
                "user_id": user_id,
                "$or": [
                    {"linkedin": linkedin_url},
                    {"linkedin_url": linkedin_url}
                ]
            })

        if lead:
            lead_status_map = {
                "profile_viewed": "linkedin_profile_viewed",
                "connection_sent": "linkedin_connection_sent",
                "connection_accepted": "linkedin_connected",
                "first_message": "linkedin_contacted",
                "message_sent": "linkedin_contacted",
                "replied": "linkedin_replied"
            }
            if new_stage in lead_status_map:
                await db.leads.update_one(
                    {"id": lead["id"]},
                    {"$set": {"status": lead_status_map[new_stage], "updated_at": now}}
                )

        return {
            "success": True,
            "previous_stage": previous_stage,
            "current_stage": new_stage,
            "transition_recorded": True,
        }

    async def _linkedin_check_daily_limit(self, input_data: Dict, ctx: Dict) -> Dict:
        """Check daily LinkedIn action limits."""
        from app.services.linkedin_scheduler_service import check_daily_limit
        user_id = input_data.get("user_id") or ctx.get("user_id", "")
        action_type = input_data.get("action_type", "connection")
        return await check_daily_limit(user_id, action_type)

    async def _linkedin_increment_daily_count(self, input_data: Dict, ctx: Dict) -> Dict:
        """Increment daily LinkedIn action counter."""
        from app.services.linkedin_scheduler_service import increment_daily_count
        user_id = input_data.get("user_id") or ctx.get("user_id", "")
        action_type = input_data.get("action_type", "connection")
        return await increment_daily_count(user_id, action_type)

    async def _linkedin_validate_session(self, input_data: Dict, ctx: Dict) -> Dict:
        """Validate LinkedIn session."""
        from app.services.linkedin_outreach_service import get_session_status
        user_id = input_data.get("user_id") or ctx.get("user_id", "")
        status = await get_session_status(user_id)
        if status.get("status") != "connected":
            return {"valid": False, "status": status.get("status", "disconnected")}
        return {"valid": True, "status": "connected"}

    # ── LinkedIn Agent Handlers ─────────────────────────────────────────────

    async def _agent_linkedin_research(self, inputs: Dict) -> Dict:
        """Execute LinkedIn research agent."""
        from app.services.linkedin_outreach_service import scrape_profile
        from app.agents.research_agent import research_lead
        import asyncio

        user_id = inputs.get("user_id", "")
        linkedin_url = inputs.get("linkedin_url", "")

        # Step 1: Scrape profile via Playwright
        profile_data = await scrape_profile(linkedin_url, user_id)

        if (not profile_data or 
            "error" in profile_data or 
            profile_data.get("success") is False or 
            not profile_data.get("name") or 
            profile_data.get("name") in ("Unknown", "Feed detail update")):
            err_msg = profile_data.get("error") if profile_data else "Empty response"
            raise ValueError(f"Failed to scrape LinkedIn profile details: {err_msg}")

        # Step 2: Research company via existing research agent
        lead_data = {
            "name": profile_data.get("name", "Unknown"),
            "company": (profile_data.get("experience", [{}])[0].get("company", "Unknown")
                        if profile_data.get("experience") else "Unknown"),
            "role": profile_data.get("headline", "Unknown"),
            "linkedin_url": linkedin_url,
        }
        research_data = await asyncio.to_thread(research_lead, lead_data)

        # Step 3: Generate personalization via generic agent runner
        if self.agents.get("linkedin_personalization_agent"):
            personalization_data = await self._run_generic_agent(
                self.agents.get("linkedin_personalization_agent"),
                {
                    "profile_data": profile_data,
                    "research_data": research_data,
                    "outreach_type": inputs.get("outreach_type", "connection_request"),
                }
            )
        else:
            logger.warning("linkedin_personalization_agent not found, skipping personalization")
            personalization_data = {}

        return {
            "profile_data": profile_data,
            "research_data": research_data,
            "personalization_data": personalization_data,
        }

    async def _agent_linkedin_research_agent(self, inputs: Dict) -> Dict:
        """Alias for linkedin_research."""
        return await self._agent_linkedin_research(inputs)

    async def _agent_linkedin_personalization(self, inputs: Dict) -> Dict:
        """Execute LinkedIn personalization agent via generic runner."""
        agent = self.agents.get("linkedin_personalization_agent")
        if not agent:
            return {"personalized_note": "", "icebreakers": [], "recommended_tone": "professional"}
        return await self._run_generic_agent(agent, inputs)

    async def _agent_linkedin_personalization_agent(self, inputs: Dict) -> Dict:
        """Alias for linkedin_personalization."""
        return await self._agent_linkedin_personalization(inputs)

    async def _agent_linkedin_message(self, inputs: Dict) -> Dict:
        """Execute LinkedIn message agent via generic runner."""
        agent = self.agents.get("linkedin_message_agent")
        if not agent:
            lead_name = inputs.get("lead_data", {}).get("name", "there")
            company = inputs.get("lead_data", {}).get("company", "your company")
            return {
                "message_text": f"Hi {lead_name}, I noticed your work at {company} and would love to connect.",
                "word_count": 15,
                "character_count": 70,
                "tone_used": "professional",
                "message_type": inputs.get("message_type", "connection_note"),
            }
        return await self._run_generic_agent(agent, inputs)

    async def _agent_linkedin_message_agent(self, inputs: Dict) -> Dict:
        """Alias for linkedin_message."""
        return await self._agent_linkedin_message(inputs)

    async def _agent_linkedin_followup(self, inputs: Dict) -> Dict:
        """Execute LinkedIn followup agent via generic runner."""
        agent = self.agents.get("linkedin_followup_agent")
        if not agent:
            return {
                "followup_message": "Hi, just following up on my earlier message.",
                "recommended_delay_hours": 72,
                "approach_used": "value-add",
                "new_value_added": "Template fallback",
            }
        return await self._run_generic_agent(agent, inputs)

    async def _agent_linkedin_followup_agent(self, inputs: Dict) -> Dict:
        """Alias for linkedin_followup."""
        return await self._agent_linkedin_followup(inputs)

    async def _agent_linkedin_campaign(self, inputs: Dict) -> Dict:
        """Execute LinkedIn campaign agent via generic runner."""
        agent = self.agents.get("linkedin_campaign_agent")
        if not agent:
            # Simple fallback: plan one action per lead
            leads = inputs.get("available_leads", [])
            plan = []
            for i, lead in enumerate(leads[:20]):
                plan.append({
                    "lead_id": lead.get("id", ""),
                    "lead_name": lead.get("name", ""),
                    "linkedin_url": lead.get("linkedin", lead.get("linkedin_url", "")),
                    "action_type": "connection_request",
                    "priority": i + 1,
                    "scheduled_day": (i // 20) + 1,
                })
            return {"execution_plan": plan, "total_actions": len(plan), "estimated_days": max(1, len(plan) // 20)}
        return await self._run_generic_agent(agent, inputs)

    async def _agent_linkedin_campaign_agent(self, inputs: Dict) -> Dict:
        """Alias for linkedin_campaign."""
        return await self._agent_linkedin_campaign(inputs)

    async def _agent_linkedin_analytics(self, inputs: Dict) -> Dict:
        """Execute LinkedIn analytics agent."""
        from app.config.mongodb_config import get_database

        db = await get_database()
        user_id = inputs.get("user_id", "")

        # Compute LinkedIn metrics from tracking_events
        connections_sent = await db.tracking_events.count_documents(
            {"user_id": user_id, "event_type": "linkedin_connection_sent", "channel": "linkedin"}
        )
        connections_accepted = await db.tracking_events.count_documents(
            {"user_id": user_id, "event_type": "linkedin_connection_accepted", "channel": "linkedin"}
        )
        messages_sent = await db.tracking_events.count_documents(
            {"user_id": user_id, "event_type": "linkedin_message_sent", "channel": "linkedin"}
        )
        replies_received = await db.tracking_events.count_documents(
            {"user_id": user_id, "event_type": "linkedin_replied", "channel": "linkedin"}
        )
        followups_sent = await db.tracking_events.count_documents(
            {"user_id": user_id, "event_type": "linkedin_followup_sent", "channel": "linkedin"}
        )
        meetings_booked = await db.linkedin_relationships.count_documents(
            {"user_id": user_id, "current_stage": "meeting_booked"}
        )
        opportunities = await db.linkedin_relationships.count_documents(
            {"user_id": user_id, "current_stage": "opportunity_created"}
        )

        acceptance_rate = (connections_accepted / connections_sent * 100) if connections_sent > 0 else 0.0
        reply_rate = (replies_received / messages_sent * 100) if messages_sent > 0 else 0.0

        return {
            "metrics": {
                "connections_sent": connections_sent,
                "connections_accepted": connections_accepted,
                "acceptance_rate": round(acceptance_rate, 2),
                "messages_sent": messages_sent,
                "replies_received": replies_received,
                "reply_rate": round(reply_rate, 2),
                "followups_sent": followups_sent,
                "meetings_booked": meetings_booked,
                "opportunities_created": opportunities,
            },
            "insights": [],
            "recommendations": [],
            "top_performing_messages": [],
        }

    async def _agent_linkedin_analytics_agent(self, inputs: Dict) -> Dict:
        """Alias for linkedin_analytics."""
        return await self._agent_linkedin_analytics(inputs)


_orchestrator_instance: Optional[Orchestrator] = None
_orchestrator_lock = asyncio.Lock()


async def get_orchestrator() -> Orchestrator:
    """Get or create the orchestrator singleton."""
    global _orchestrator_instance
    if _orchestrator_instance is not None:
        return _orchestrator_instance
    async with _orchestrator_lock:
        if _orchestrator_instance is None:
            _orchestrator_instance = Orchestrator()
            await _orchestrator_instance.initialize()
    return _orchestrator_instance