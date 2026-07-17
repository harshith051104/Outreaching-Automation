import logging
from orchestrator.registry import SkillConfig
from orchestrator.context import ExecutionContext
from orchestrator.skill_runtime import SkillRuntime

logger = logging.getLogger("VerifySkillRuntime")

class MockLLMInterface:
    def __init__(self):
        self.calls = []
        
    async def generate_completion(self, task_type, messages, user_id, temperature, workflow_run_id):
        self.calls.append({
            "task_type": task_type,
            "messages": messages,
            "user_id": user_id,
            "temperature": temperature,
            "workflow_run_id": workflow_run_id
        })
        return {
            "provider": "groq",
            "model": "llama-3.3-70b-versatile",
            "content": '{"personalized_body": "Hello Shivam from DeepTech Corp! Here is our value prop."}'
        }

class MockRegistry:
    def get_skill(self, name):
        # Return a real SkillConfig instantiated with Markdown content format
        md_content = f"""# {name}

## Purpose
Mock skill for testing prompt rendering and validation

## Inputs
lead_name: string
company_name: string

## Outputs
personalized_body: string

## Execution Steps
- Format the greeting
- Insert value prop

## Validation Rules
- Must mention lead name
"""
        return SkillConfig(name, None, md_content)

class MockDispatcher:
    def has_tool(self, name):
        return False

async def run_test() -> bool:
    logger.info("[*] Running Skill Runtime Verification...")
    
    registry = MockRegistry()
    dispatcher = MockDispatcher()
    llm = MockLLMInterface()
    
    runtime = SkillRuntime(registry=registry, dispatcher=dispatcher, llm_interface=llm)
    context = ExecutionContext(variables={"lead_name": "Shivam", "company_name": "DeepTech Corp"})
    
    # Run the skill execution (calls dynamic LLM path)
    res = await runtime.execute(
        skill_name="personalize_email",
        inputs={"lead_name": "Shivam", "company_name": "DeepTech Corp"},
        context=context,
        workflow_run_id="wrun_test_123"
    )
    
    # Verifications
    if not res or "personalized_body" not in res:
        logger.error(f"[-] Invalid or empty response: {res}")
        return False
        
    if len(llm.calls) != 1:
        logger.error(f"[-] Expected 1 LLM call, got {len(llm.calls)}")
        return False
        
    llm_call = llm.calls[0]
    sys_prompt = next(m["content"] for m in llm_call["messages"] if m["role"] == "system")
    
    # Check prompt rendering contains steps and purpose
    if "Mock skill for testing prompt rendering" not in sys_prompt:
        logger.error("[-] System prompt did not render skill purpose")
        return False
        
    if "Format the greeting" not in sys_prompt:
        logger.error("[-] System prompt did not render execution steps")
        return False
        
    logger.info(f"[+] Rendered Prompt Checked. Output generated: {res}")
    logger.info("[+] Skill Runtime Verification: PASSED")
    return True
