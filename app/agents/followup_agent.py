"""
Follow-up Agent — Generates strategic follow-up emails that re-engage
prospects without being pushy.

Considers engagement signals, sequence position, and previous messaging
to vary the approach across the follow-up sequence.
"""

import json
import logging
import re
from typing import Any

from app.config.groq_config import groq_inference

logger = logging.getLogger(__name__)

SEQUENCE_VARIATIONS = {
    1: "value-add — share a relevant insight, article, or resource",
    2: "social-proof — share a customer success story or metric",
    3: "urgency — legitimate business reason to respond",
    4: "breakup — respectful final outreach, make it easy to say no",
}


def generate_followup(
    original_email: dict,
    lead_data: dict,
    sequence_number: int,
    engagement_data: dict,
    user_id: str | None = None,
) -> dict[str, Any]:
    """
    Generate a follow-up email framework-freely.

    Args:
        original_email: The original email (subject, body_text, body_html).
        lead_data: Lead information.
        sequence_number: Follow-up sequence number (1-based).
        engagement_data: Engagement signals for this lead.

    Returns:
        Follow-up email data as a dictionary.
    """
    lead_name = lead_data.get("name", "Unknown")
    company = lead_data.get("company", "Unknown")
    role = lead_data.get("role", "Unknown")
    sender_name = lead_data.get("sender_name", "").strip()
    if not sender_name:
        sender_name = "Founder"

    original_subject = original_email.get("subject", "")
    original_body = original_email.get("body_text", "")

    reply_snippet = engagement_data.get("reply_snippet", "") if engagement_data else ""
    reply_classification = engagement_data.get("classification", "") if engagement_data else ""

    engagement_json = json.dumps(engagement_data, indent=2, default=str)

    approach = SEQUENCE_VARIATIONS.get(
        sequence_number,
        SEQUENCE_VARIATIONS.get(4, "breakup — respectful final outreach"),
    )

    logger.info(f"Generating framework-free follow-up #{sequence_number} for: {lead_name} signed by: {sender_name}")

    system_prompt = (
        "You are a Follow-up Strategist sales expert. You are a persistence expert in sales follow-ups with a proven "
        "track record of turning cold leads warm through thoughtful, well-timed follow-up sequences. You understand "
        "that 80% of deals require 5+ touchpoints, and that the key to effective follow-ups is adding NEW value with each touch — "
        "never just 'bumping this to the top of your inbox.' You're a master at reading engagement signals and crafting "
        "follow-ups that address the likely reason for silence."
    )

    reply_context = ""
    if reply_snippet:
        reply_context = f"""
**Lead's Previous Reply:**
---
{reply_snippet}
---

**Classification of Lead's Reply:** {reply_classification}
"""

    user_prompt = f"""
You are a Follow-up Strategist. Generate follow-up email #{sequence_number} for {lead_name} ({role} at {company}) sent by {sender_name}.

**CRITICAL INSTRUCTION: You MUST analyze the content below and use SPECIFIC details from it in your email. Do NOT generate generic templates.**

{reply_context}
**Original Email (MUST ANALYZE AND REFERENCE):**
Subject: {original_subject}
Body:
{original_body}

**Lead Profile (MUST USE AT LEAST ONE SPECIFIC DETAIL):**
- Name: {lead_name}
- Role: {role}
- Company: {company}

**Sender Info:**
- Sender Name: {sender_name}

**Engagement Signals:**
{engagement_json}

**Sequence Position:** Follow-up #{sequence_number}
**Recommended Approach:** {approach}

**Follow-up Strategy Guidelines:**

1. **ANALYZE THE ORIGINAL EMAIL ABOVE** — Extract a specific point to reference (their role, a topic they mentioned, a question they asked, etc.)

2. **ANALYZE THE LEAD PROFILE** — Use their actual role, company, or other specific details. NOT generic phrases like "your company."

3. **Read the engagement signals:**
   - No opens → Subject line failed. Try a completely different angle.
   - Opens but no reply → Content didn't resonate. Change the value prop.
   - Multiple opens → Interested but hesitant. Lower the barrier to engage.
   - Clicked but no reply → Very interested. Be direct about next steps.
   - Lead replied with interest → Respond to their specific interest/questions

4. **Approach by Sequence Number:**
   - Follow-up 1 (Value-Add): Share a relevant resource, insight, or case study
   - Follow-up 2 (Social Proof): Share a relevant customer story or result
   - Follow-up 3 (Urgency): Create legitimate urgency (market timing, limited offer)
   - Follow-up 4+ (Breakup): Respectful final outreach, make it easy to say no

5. **When lead has replied with interest:**
   - Acknowledge what they said specifically
   - If they want to learn more, offer specific information
   - If they requested a demo/meeting, send a calendar link or specific times

6. **Technical Requirements:**
   - Keep under 100 words (follow-ups should be shorter than initial emails)
   - Use a different subject line approach (reply thread "Re:" or new subject)
   - Single clear CTA
   - No spam triggers
   - Both HTML and plain-text versions
   - SIGN OFF using the sender's name '{sender_name}'

**FORBIDDEN — Your email will be rejected if it contains:**
- Generic phrases like "I hope this email finds you well"
- Generic placeholders like '[Your Name]' or '[Your Email]'
- Content that could work for any prospect (must be specific to THIS lead)
- "Just checking in" without adding new value

Return your output strictly as a JSON object matching this structure:
{{
    "subject": "follow-up subject line",
    "body_html": "<p>HTML version...</p>",
    "body_text": "Plain text version...",
    "recommended_delay_hours": 96,
    "approach_used": "value-add|social-proof|urgency|breakup",
    "new_value_added": "Brief description of what new value this follow-up adds",
    "is_reply_thread": true,
    "specific_details_used": ["list of specific details you used from the inputs"]
}}
"""

    try:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        raw_output = groq_inference(messages, temperature=0.5, user_id=user_id)
        parsed = _extract_json(raw_output)
        logger.info("Follow-up generation completed framework-freely — JSON parsed successfully.")
        return parsed
    except Exception as exc:
        logger.warning(f"Could not generate follow-up framework-freely: {exc}")
        
        # Simple fallback template
        fallback_subject = f"Re: {original_subject}"
        fallback_body = (
            f"Hi {lead_name},\n\n"
            f"I wanted to follow up on my previous email. I know you are busy, but I'd love to connect "
            f"briefly next week to see if we can help optimize operations at {company}.\n\n"
            f"Would you be open to a 10-minute chat?\n\n"
            f"Best regards,\n"
            f"{sender_name}"
        )
        return {
            "subject": fallback_subject,
            "body_html": f"<p>{fallback_body.replace(chr(10), '<br>')}</p>",
            "body_text": fallback_body,
            "recommended_delay_hours": 96,
            "approach_used": "value-add",
            "new_value_added": "Follow-up check-in",
            "is_reply_thread": True
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