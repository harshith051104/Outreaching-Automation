import logging
import asyncio
import hashlib
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml
import re

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

class MetadataRegistry:
    """Read-only Configuration Manager for all workflow agent metadata."""
    def __init__(self, base_path: Optional[Path] = None, auto_reload: bool = True, reload_interval: int = 5):
        self.base_path = base_path or Path(__file__).parent.parent
        self.auto_reload = auto_reload
        self.reload_interval = reload_interval
        
        self._agents: Dict[str, AgentConfig] = {}
        self._skills: Dict[str, SkillConfig] = {}
        self._workflows: Dict[str, WorkflowConfig] = {}
        self._tools: Dict[str, ToolConfig] = {}
        self._memory_registry: Dict[str, Any] = {}
        
        self.registry_version: str = ""
        self.loaded_at: float = 0.0
        self._file_hashes: Dict[str, str] = {}
        self._watch_task: Optional[asyncio.Task] = None
        self._reload_callbacks: List[callable] = []

    def register_reload_callback(self, callback: callable) -> None:
        """Register a callback to trigger on registry reload (e.g. Workflow Compiler recompile)."""
        self._reload_callbacks.append(callback)

    def get_agent(self, agent_id: str) -> Optional[AgentConfig]:
        return self._agents.get(agent_id)

    def get_skill(self, skill_id: str) -> Optional[SkillConfig]:
        return self._skills.get(skill_id)

    def get_workflow(self, workflow_id: str) -> Optional[WorkflowConfig]:
        return self._workflows.get(workflow_id)

    def get_tool(self, tool_id: str) -> Optional[ToolConfig]:
        return self._tools.get(tool_id)

    def get_memory_registry(self) -> Dict[str, Any]:
        return self._memory_registry

    async def initialize(self) -> None:
        """Load and cache configs."""
        await self.reload()
        if self.auto_reload and not self._watch_task:
            self._watch_task = asyncio.create_task(self._watch_files_loop())

    async def reload(self) -> bool:
        """Load all metadata files from disk. Return True if any file changed."""
        logger.info("MetadataRegistry: Loading config files from disk...")
        
        new_file_hashes = {}
        changed = False

        # Load Tools
        tools_path = self.base_path / "tools" / "tools.yaml"
        if tools_path.exists():
            h = self._compute_file_hash(tools_path)
            new_file_hashes[str(tools_path)] = h
            if self._file_hashes.get(str(tools_path)) != h:
                changed = True
                
        # Load Memory Registry
        memory_path = self.base_path / "memory" / "memory_registry.yaml"
        if memory_path.exists():
            h = self._compute_file_hash(memory_path)
            new_file_hashes[str(memory_path)] = h
            if self._file_hashes.get(str(memory_path)) != h:
                changed = True

        # Load Agents
        agents_dir = self.base_path / "agents"
        agent_files = list(agents_dir.glob("*.md")) if agents_dir.exists() else []
        for f in agent_files:
            h = self._compute_file_hash(f)
            new_file_hashes[str(f)] = h
            if self._file_hashes.get(str(f)) != h:
                changed = True

        # Load Skills
        skills_dir = self.base_path / "skills"
        skill_files = list(skills_dir.glob("*.md")) if skills_dir.exists() else []
        for f in skill_files:
            h = self._compute_file_hash(f)
            new_file_hashes[str(f)] = h
            if self._file_hashes.get(str(f)) != h:
                changed = True

        # Load Workflows
        workflows_dir = self.base_path / "workflows"
        workflow_files = list(workflows_dir.glob("*.yaml")) if workflows_dir.exists() else []
        for f in workflow_files:
            h = self._compute_file_hash(f)
            new_file_hashes[str(f)] = h
            if self._file_hashes.get(str(f)) != h:
                changed = True

        # Check for deleted files
        if len(new_file_hashes) != len(self._file_hashes):
            changed = True

        if not changed and self.registry_version:
            logger.info("MetadataRegistry: No config files changed.")
            return False

        # Load content
        self._file_hashes = new_file_hashes
        
        # Tools
        if tools_path.exists():
            try:
                data = yaml.safe_load(tools_path.read_text(encoding="utf-8"))
                self._tools = {}
                if data and isinstance(data, dict):
                    for tool_name, tool_config in data.get("tools", {}).items():
                        self._tools[tool_name] = ToolConfig(tool_name, tool_config)
            except Exception as e:
                logger.error(f"Failed to load tools: {e}")

        # Memory Registry
        if memory_path.exists():
            try:
                self._memory_registry = yaml.safe_load(memory_path.read_text(encoding="utf-8")) or {}
            except Exception as e:
                logger.error(f"Failed to load memory registry: {e}")

        # Agents
        self._agents = {}
        for f in agent_files:
            try:
                content = f.read_text(encoding="utf-8")
                if not content.strip() or "deprecated" in content.lower():
                    continue
                frontmatter, body = self._parse_yaml_frontmatter(content)
                agent_name = f.stem
                self._agents[agent_name] = AgentConfig(agent_name, f, frontmatter, body)
            except Exception as e:
                logger.error(f"Failed to load agent {f}: {e}")

        # Skills
        self._skills = {}
        for f in skill_files:
            try:
                content = f.read_text(encoding="utf-8")
                if not content.strip() or "deprecated" in content.lower():
                    continue
                skill_name = f.stem
                self._skills[skill_name] = SkillConfig(skill_name, f, content)
            except Exception as e:
                logger.error(f"Failed to load skill {f}: {e}")

        # Workflows
        self._workflows = {}
        for f in workflow_files:
            try:
                content = f.read_text(encoding="utf-8")
                if not content.strip() or "deprecated" in content.lower():
                    continue
                data = yaml.safe_load(content)
                if not data or not isinstance(data, dict):
                    continue
                workflow_name = data.get("name", f.stem)
                self._workflows[workflow_name] = WorkflowConfig(workflow_name, f, data)
            except Exception as e:
                logger.error(f"Failed to load workflow {f}: {e}")

        # Compute Registry Version Hash
        combined_hash = hashlib.md5("".join(sorted(self._file_hashes.values())).encode("utf-8")).hexdigest()
        self.registry_version = combined_hash
        self.loaded_at = time.time()
        logger.info(f"MetadataRegistry: Loaded config version {self.registry_version} successfully.")

        # Notify callbacks
        for callback in self._reload_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback())
                else:
                    callback()
            except Exception as e:
                logger.error(f"Reload callback failed: {e}")

        return True

    def health(self) -> Dict[str, Any]:
        """Expose registry health details for telemetry & diagnostics."""
        return {
            "status": "healthy" if self.registry_version else "uninitialized",
            "version": self.registry_version,
            "last_reload": self.loaded_at,
            "agents_count": len(self._agents),
            "skills_count": len(self._skills),
            "workflows_count": len(self._workflows),
            "tools_count": len(self._tools),
        }

    def _compute_file_hash(self, path: Path) -> str:
        try:
            content = path.read_bytes()
            return hashlib.md5(content).hexdigest()
        except Exception:
            return ""

    def _parse_yaml_frontmatter(self, content: str) -> tuple[Dict, str]:
        pattern = r"^---\n(.*?)\n---\n(.*)$"
        match = re.match(pattern, content, re.DOTALL)
        if match:
            try:
                frontmatter = yaml.safe_load(match.group(1)) or {}
            except Exception:
                frontmatter = {}
            body = match.group(2)
            return frontmatter, body
        return {}, content

    async def _watch_files_loop(self) -> None:
        """Background file monitoring loop."""
        while True:
            await asyncio.sleep(self.reload_interval)
            try:
                await self.reload()
            except Exception as e:
                logger.error(f"Error in file monitor watch loop: {e}")

    async def stop(self) -> None:
        """Stop background monitors."""
        if self._watch_task:
            self._watch_task.cancel()
            self._watch_task = None
