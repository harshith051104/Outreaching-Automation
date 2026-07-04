"""
Reply Classification Agent — Classifies email reply intent and sentiment
to prioritize leads and determine next actions.

Uses NLP expertise to analyze replies and produce structured classifications.
"""

import json
import logging
import re
from typing import Any

from app.config.groq_config import groq_inference

logger = logging.getLogger(__name__)


def classify_reply(
    reply_text: str,
    original_email: str,
    lead_context: dict,
    user_id: str | None = None,
) -> dict[str, Any]:
    """
    Classify an email reply framework-freely.

    Args:
        reply_text: The reply email text.
        original_email: The original outreach email.
        lead_context: Context about the lead.
        user_id: The ID of the user owning the campaign.

    Returns:
        Classification result as a dictionary.
    """
    lead_name = lead_context.get("name", "Unknown")
    company = lead_context.get("company", "Unknown")
    role = lead_context.get("role", "Unknown")
    current_score = lead_context.get("lead_score", 50)

    logger.info(f"Classifying reply framework-freely from: {lead_name} for user={user_id}")

    system_prompt = (
        "You are a Reply Intent Classifier sales NLP expert. You specialize in B2B sales communication analysis "
        "and building intent classifiers. You can detect subtle cues in email replies that indicate buying intent, "
        "hesitation, objections, or disinterest. Your accuracy is paramount because your classifications drive "
        "automation routing leads to appropriate follow-up tracks."
    )

    user_prompt = f"""
Classify the following email reply to determine the lead's intent, sentiment,
and the recommended next action.

**Lead Context:**
- Name: {lead_name}
- Role: {role}
- Company: {company}
- Current Lead Score: {current_score}/100

**Original Outreach Email:**
---
{original_email}
---

**Reply Received:**
---
{reply_text}
---

**Classification Categories:**

1. **interested** — The lead expresses interest, asks questions, or wants to learn more.
   Examples: "Tell me more", "What does pricing look like?", "This sounds relevant"

2. **meeting_requested** — The lead explicitly agrees to or requests a meeting/call.
   Examples: "Let's set up a call", "I'm free Thursday", "Send me a calendar link"

3. **not_interested** — The lead clearly declines or indicates no interest.
   Examples: "Not interested", "Please remove me", "We already have a solution"

4. **follow_up_later** — The lead indicates timing is wrong but doesn't reject outright.
   Examples: "Not right now", "Reach out next quarter", "We're in a freeze"

5. **spam** — Auto-reply, out-of-office, bounce notification, or system mailer messages. Note: Do NOT classify friendly personal greetings, casual conversations, or short queries (such as "How are you?", "Who is this?", or "Thanks") as spam. Classify those as interested/neutral.
   Examples: "I'm OOO until...", "This mailbox is not monitored", auto-generated replies

**Analysis Requirements:**
- Classify into exactly one of the five categories above
- Detect overall sentiment: positive, neutral, or negative
- Assign a confidence score (0.0 to 1.0)
- Calculate a lead score adjustment:
  - interested: +10 to +20
  - meeting_requested: +25 to +40
  - not_interested: -30 to -50
  - follow_up_later: -5 to +5
  - spam: 0
- Explain your reasoning in 2-3 sentences
- Suggest the recommended next action

Return your output strictly as a JSON object matching this structure:
{{
    "classification": "interested|meeting_requested|not_interested|follow_up_later|spam",
    "sentiment": "positive|neutral|negative",
    "confidence_score": 0.85,
    "lead_score_delta": 15,
    "reasoning": "The reply shows clear interest because...",
    "key_signals": ["asked about pricing", "mentioned timeline"],
    "recommended_action": "Schedule a discovery call within 24 hours",
    "urgency": "high|medium|low"
}}
"""

    try:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        raw_output = groq_inference(messages, temperature=0.3, user_id=user_id)
        parsed = _extract_json(raw_output)
        logger.info("Reply classification completed framework-freely — JSON parsed successfully.")
        return parsed
    except Exception as exc:
        logger.warning(f"Could not parse classification output framework-freely: {exc}")
        return {
            "classification": "follow_up_later",
            "sentiment": "neutral",
            "confidence_score": 0.3,
            "lead_score_delta": 0,
            "reasoning": "Unable to parse structured classification.",
            "key_signals": [],
            "recommended_action": "Manual review required.",
            "urgency": "low",
        }


def _extract_json(text: str) -> dict:
    """Extract and parse the first JSON object found in a text string."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if json_match:
        return json.loads(json_match.group(1))

    brace_start = text.find("{")
    if brace_start != -1:
        depth = 0
        for i in range(brace_start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    return json.loads(text[brace_start : i + 1])

    raise ValueError("No valid JSON found in text.")