"""
Groq LLM configuration.

Groq provides fast inference with the llama-3.3-70b-versatile model.
"""

import logging
from typing import Any
from groq import Groq
from app.config.settings import settings

logger = logging.getLogger(__name__)

_groq_client = None
_disabled_sections = {
    "linkedin": False,
    "reply_monitor": False,
    "campaigns": False,
    "chatbot": False,
}

def set_llm_section_disabled(section: str, disabled: bool) -> None:
    """Set the LLM disabled state for a specific section."""
    global _disabled_sections
    if section in _disabled_sections:
        _disabled_sections[section] = disabled
        logger.info(f"LLM section '{section}' disabled set to: {disabled}")

def get_llm_section_disabled(section: str) -> bool:
    """Get the LLM disabled state for a specific section."""
    global _disabled_sections
    return _disabled_sections.get(section, False)

def set_llm_disabled(disabled: bool) -> None:
    """Set the LLM disabled state globally (for backwards compatibility)."""
    global _disabled_sections
    for section in _disabled_sections:
        _disabled_sections[section] = disabled
    logger.info(f"Global LLM disabled status set to: {disabled}")

def get_llm_disabled() -> bool:
    """Get the global LLM disabled state (returns True if linkedin is disabled as fallback)."""
    global _disabled_sections
    # Auto-detect from call stack
    import inspect
    frame = inspect.currentframe()
    try:
        current_frame = frame
        for _ in range(5):
            if not current_frame:
                break
            module_name = current_frame.f_globals.get("__name__", "")
            if "reply_classification" in module_name or "followup" in module_name or "reply_monitor" in module_name:
                return _disabled_sections.get("reply_monitor", False)
            if "research" in module_name or "personalization" in module_name or "outreach_writer" in module_name:
                return _disabled_sections.get("campaigns", False)
            if "content_strategy" in module_name:
                return _disabled_sections.get("linkedin", False)
            current_frame = current_frame.f_back
    finally:
        del frame
    return _disabled_sections.get("linkedin", False)

def run_async_fallback(coro):
    import asyncio
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import threading
        from queue import Queue

        q = Queue()

        def worker():
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            try:
                res = new_loop.run_until_complete(coro)
                q.put((True, res))
            except Exception as e:
                q.put((False, e))
            finally:
                new_loop.close()

        t = threading.Thread(target=worker)
        t.start()
        t.join()
        success, val = q.get()
        if success:
            return val
        raise val
    else:
        new_loop = asyncio.new_event_loop()
        try:
            return new_loop.run_until_complete(coro)
        finally:
            new_loop.close()

_user_groq_clients = {}

def get_groq_client(user_id: str | None = None) -> Groq:
    """Get the Groq client, resolving per-user keys if user_id is provided."""
    global _groq_client
    if not user_id:
        if _groq_client is None:
            _groq_client = Groq(api_key=settings.GROQ_API_KEY)
        return _groq_client

    # Resolve api key for user_id
    from app.services.integrations_service import get_api_key_sync
    
    # Run sync get_api_key
    api_key = get_api_key_sync(user_id, "groq", settings.GROQ_API_KEY)
    
    if not api_key or api_key == settings.GROQ_API_KEY:
        if _groq_client is None:
            _groq_client = Groq(api_key=settings.GROQ_API_KEY)
        return _groq_client

    if api_key not in _user_groq_clients:
        _user_groq_clients[api_key] = Groq(api_key=api_key)
    return _user_groq_clients[api_key]

def groq_inference(
    messages: list[dict[str, str]],
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 2048,
    section: str | None = None,
    user_id: str | None = None,
) -> str:
    """
    Execute direct chat completions via the active provider.
    """
    if not section:
        # Auto-detect from prompt contents or stack
        prompt_lower = ""
        if messages:
            prompt_lower = messages[-1].get("content", "").lower()
            
        if "sentiment" in prompt_lower or "classify" in prompt_lower:
            section = "reply_monitor"
        elif "connection" in prompt_lower or "note" in prompt_lower:
            section = "linkedin"
        elif "research" in prompt_lower or "scrape" in prompt_lower or "profile" in prompt_lower:
            section = "campaigns"
        elif "follow" in prompt_lower or "sequence" in prompt_lower:
            section = "campaigns"
        else:
            section = "chatbot"
            
        # Overwrite by stack inspection
        import inspect
        frame = inspect.currentframe()
        try:
            current_frame = frame
            for _ in range(5):
                if not current_frame:
                    break
                module_name = current_frame.f_globals.get("__name__", "")
                if "reply_classification" in module_name or "followup" in module_name or "reply_monitor" in module_name:
                    section = "reply_monitor"
                    break
                if "research" in module_name or "personalization" in module_name or "outreach_writer" in module_name:
                    section = "campaigns"
                    break
                if "content_strategy" in module_name:
                    section = "linkedin"
                    break
                current_frame = current_frame.f_back
        finally:
            del frame

    if get_llm_section_disabled(section):
        logger.info(f"LLM is disabled for section '{section}'. Returning mock response.")
        prompt_lower = ""
        if messages:
            prompt_lower = messages[-1].get("content", "").lower()
            
        # Match prompt intent to return corresponding mock responses
        if "sentiment" in prompt_lower or "classify" in prompt_lower:
            return '{"classification": "interested", "sentiment": "positive", "lead_score_delta": 15}'
        elif "connection" in prompt_lower or "note" in prompt_lower:
            return "Hi, I saw your profile and was impressed by your experience. I would love to connect and keep in touch!"
        elif "research" in prompt_lower or "scrape" in prompt_lower or "profile" in prompt_lower:
            return '{"lead_summary": "Experienced professional in target domain.", "company_summary": "Innovating growth company.", "pain_points": [], "outreach_angles": []}'
        elif "follow" in prompt_lower or "sequence" in prompt_lower:
            return "Hi,\n\nFollowing up on my previous message. Let me know if you have a few minutes to chat next week.\n\nBest,\n[Name]"
        elif "analytics" in prompt_lower or "insights" in prompt_lower or "performance" in prompt_lower:
            return '{"summary": {"overview": "Campaign is performing strongly with high deliverability and steady engagement.", "performance_grade": "B", "top_wins": ["High email open rates", "Stable delivery metrics"], "top_concerns": ["Slightly below-average click-through rate"]}, "key_metrics": {"open_rate": {"value": 25.0, "benchmark": 21.5, "status": "above"}, "click_rate": {"value": 1.5, "benchmark": 2.3, "status": "below"}, "reply_rate": {"value": 0.8, "benchmark": 1.0, "status": "below"}, "bounce_rate": {"value": 1.2, "benchmark": 2.0, "status": "below"}}, "campaign_comparison": {"comparison_summary": "Performing within target benchmarks relative to historical sequences.", "key_differentiators": ["High quality personalization hooks"]}, "learning_memory_insights": {"lessons_applied": ["Personalized subject lines increase open rate"], "new_insights_recorded": []}, "trends": ["Engagement peaks on weekday mornings"], "whats_working": [{"element": "Subject lines", "why": "Curiosity and directness drive opens", "amplify_how": "Scale similar styles"}], "whats_not_working": [{"element": "Body CTA", "why": "Needs lower friction ask", "root_cause": "Requesting 15m too early", "fix": "Change to yes/no question"}], "recommendations": [{"priority": 1, "action": "Lower CTA friction to a soft reply request", "expected_impact": "Improve reply rate by 10-15%", "effort": "low", "timeline": "immediate"}], "top_performing_leads": []}'
        else:
            return f"This is a mock LLM response generated because LLM calls are paused for {section}."

    provider = getattr(settings, "LLM_PROVIDER", "groq").lower()
    
    if provider == "nvidia":
        from app.services.integrations_service import get_api_key_sync
        api_key = get_api_key_sync(user_id, "nvidia", settings.NVIDIA_NIM_API_KEY)
        model_name = model or settings.NVIDIA_NIM_MODEL or "moonshotai/kimi-k2.6"
        completion = openai_compatible_inference(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=api_key,
            model=model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        return completion.choices[0].message.content or ""
        
    elif provider == "xiaomi":
        from app.services.integrations_service import get_api_key_sync
        api_key = get_api_key_sync(user_id, "xiaomi", settings.XIAOMI_API_KEY)
        model_name = model or settings.XIAOMI_MODEL or "mimo-v2.5"
        completion = openai_compatible_inference(
            base_url="https://api.xiaomimimo.com/v1",
            api_key=api_key,
            model=model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        return completion.choices[0].message.content or ""
        
    else:
        client = get_groq_client(user_id)
        model_name = model or settings.GROQ_MODEL or "llama-3.3-70b-versatile"
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"Groq inference failed: {e}")
            raise e

# ── OpenAI Compatible Custom Client Mock ────────────────────────────────────

class NvidiaToolCallFunction:
    def __init__(self, name: str, arguments: str):
        self.name = name
        self.arguments = arguments

class NvidiaToolCall:
    def __init__(self, id: str, type: str, function: NvidiaToolCallFunction):
        self.id = id
        self.type = type
        self.function = function

class NvidiaMessage:
    def __init__(self, content: str | None, tool_calls: list | None = None):
        self.content = content
        self.tool_calls = tool_calls

class NvidiaChoice:
    def __init__(self, message: NvidiaMessage):
        self.message = message

class NvidiaCompletion:
    def __init__(self, choices: list[NvidiaChoice]):
        self.choices = choices

def openai_compatible_inference(
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    temperature: float = 0.7,
    max_tokens: int = 2048,
    tools: list | None = None,
    tool_choice: str | dict | None = None,
) -> NvidiaCompletion:
    import httpx
    import json
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if tools:
        payload["tools"] = tools
    if tool_choice:
        payload["tool_choice"] = tool_choice
        
    try:
        response = httpx.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers=headers,
            json=payload,
            timeout=120.0
        )
        response.raise_for_status()
        data = response.json()
        
        choices = []
        for choice_data in data.get("choices", []):
            msg_data = choice_data.get("message", {})
            content = msg_data.get("content")
            
            tool_calls = None
            raw_tool_calls = msg_data.get("tool_calls")
            if raw_tool_calls:
                tool_calls = []
                for tc in raw_tool_calls:
                    func_data = tc.get("function", {})
                    args_val = func_data.get("arguments", "{}")
                    if isinstance(args_val, dict):
                        args_str = json.dumps(args_val)
                    else:
                        args_str = str(args_val)
                        
                    func_obj = NvidiaToolCallFunction(
                        name=func_data.get("name", ""),
                        arguments=args_str
                    )
                    tool_calls.append(NvidiaToolCall(
                        id=tc.get("id", ""),
                        type=tc.get("type", "function"),
                        function=func_obj
                    ))
            
            msg_obj = NvidiaMessage(content=content, tool_calls=tool_calls)
            choices.append(NvidiaChoice(message=msg_obj))
            
        return NvidiaCompletion(choices=choices)
    except Exception as e:
        logger.error(f"Inference failed for {base_url} ({model}): {e}")
        raise e

def llm_chat_completion(
    messages: list[dict[str, str]],
    model: str | None = None,
    provider: str | None = None,
    tools: list | None = None,
    tool_choice: str | dict | None = None,
    temperature: float = 0.3,
    max_tokens: int = 2048,
    user_id: str | None = None,
) -> Any:
    """
    Execute chat completions dynamically based on provider and model.
    """
    active_provider = provider
    if not active_provider:
        active_provider = getattr(settings, "LLM_PROVIDER", "nvidia")
    active_provider = active_provider.lower()
    
    if active_provider == "nvidia":
        from app.services.integrations_service import get_api_key_sync
        api_key = get_api_key_sync(user_id, "nvidia", settings.NVIDIA_NIM_API_KEY)
        model_name = model or settings.NVIDIA_NIM_MODEL or "moonshotai/kimi-k2.6"
        return openai_compatible_inference(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=api_key,
            model=model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
            tool_choice=tool_choice
        )
    elif active_provider == "xiaomi":
        from app.services.integrations_service import get_api_key_sync
        api_key = get_api_key_sync(user_id, "xiaomi", settings.XIAOMI_API_KEY)
        model_name = model or settings.XIAOMI_MODEL or "mimo-v2.5"
        return openai_compatible_inference(
            base_url="https://api.xiaomimimo.com/v1",
            api_key=api_key,
            model=model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
            tool_choice=tool_choice
        )
    else:
        # groq
        client = get_groq_client(user_id)
        model_name = model or settings.GROQ_MODEL or "llama-3.3-70b-versatile"
        
        kwargs = {
            "model": model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
        if tool_choice:
            kwargs["tool_choice"] = tool_choice
            
        return client.chat.completions.create(**kwargs)