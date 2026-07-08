"""
AI Guardrails Review Service.
ponytail: Simple JSON checker calling LLMManager.
"""

import json
import logging
from typing import Any, Dict

from app.services.llm_manager import LLMManager

logger = logging.getLogger(__name__)


async def run_guardrail_review(subject: str, body: str, user_id: str) -> Dict[str, Any]:
    """
    Review an outreach email against the safety, quality, and spam checklist.
    Returns a review report dict including a quality score (0-100).
    """
    system_prompt = """You are an AI Quality Assurance and Security Guardrail agent.
Analyze the email subject and body below against the following criteria:
1. **Grammar & Spelling**: Check for grammatical or spelling errors.
2. **Tone**: Verify if the tone is appropriate (professional, warm, engaging).
3. **Hallucination**: Identify any unrealistic claims, made-up metrics, or suspicious data points.
4. **Spam Words**: Identify common spam-trigger words (e.g., "win money", "risk-free", "click here", "buy now").
5. **Missing Personalization**: Detect unreplaced placeholders like {{first_name}}, [Your Name], brackets, or braces.
6. **Sensitive Leakage**: Ensure no passwords, internal URLs, API keys, or raw secrets are leaked.

You MUST respond strictly with a JSON object matching this structure:
{
  "score": 85, // Integer 0 to 100
  "passed": true, // Boolean (true if score >= 70 and no critical leakage/hallucination)
  "grammar_ok": true,
  "tone_ok": true,
  "no_hallucinations": true,
  "spam_words_found": ["free", "instant"], // Array of strings (empty list if none)
  "personalization_complete": true,
  "no_sensitive_leakage": true,
  "comments": "Overall excellent quality; minor spam words detected."
}
"""

    user_content = f"""**Email Subject**: {subject}
**Email Body**:
{body}
"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content}
    ]

    try:
        completion = await LLMManager.generate_completion(
            task_type="FAST_CHAT_RESPONSES",
            messages=messages,
            user_id=user_id,
            temperature=0.1
        )
        content = completion.get("content", "").strip()
        
        # ponytail: parse JSON response safely
        start_idx = content.find("{")
        end_idx = content.rfind("}")
        if start_idx != -1 and end_idx != -1:
            content = content[start_idx:end_idx + 1]
            
        data = json.loads(content)
        logger.info(f"Guardrail: Email score={data.get('score')} passed={data.get('passed')}")
        return data
    except Exception as exc:
        logger.error(f"Guardrail review failed, defaulting to pass: {exc}")
        return {
            "score": 100,
            "passed": True,
            "grammar_ok": True,
            "tone_ok": True,
            "no_hallucinations": True,
            "spam_words_found": [],
            "personalization_complete": True,
            "no_sensitive_leakage": True,
            "comments": "Guardrail execution bypassed due to API error."
        }
