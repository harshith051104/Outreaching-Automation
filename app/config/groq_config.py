"""
Groq LLM configuration.

Groq provides fast inference with the llama-3.3-70b-versatile model.
"""

import logging
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

def get_groq_client() -> Groq:
    """Get or initialize the Groq client singleton."""
    global _groq_client
    if _groq_client is None:
        _groq_client = Groq(api_key=settings.GROQ_API_KEY)
    return _groq_client

def groq_inference(
    messages: list[dict[str, str]],
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 2048,
    section: str | None = None,
) -> str:
    """
    Execute direct chat completions via Groq.
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

    client = get_groq_client()
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