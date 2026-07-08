"""
Content Strategy Agent — Generates LinkedIn outreach content and calendar prompts.

Creates personalized LinkedIn connection requests, follow-up messages,
and meeting content based on lead research data, plus multi-channel
campaign calendars (email, LinkedIn, call, task).
"""

import json
import logging
import re
from typing import Any

from app.config.groq_config import groq_inference

logger = logging.getLogger(__name__)


import datetime
import uuid
from app.config.mongodb_config import get_database

async def generate_linkedin_calendar(
    user_id: str,
    campaign_id: str,
    campaign_goal: str,
    target_audience: str,
    industry: str,
) -> dict[str, Any]:
    """
    Generate a strategic 30-day LinkedIn posting content calendar.
    """
    logger.info(f"Generating LinkedIn content calendar for campaign: {campaign_id}")

    system_prompt = (
        "You are an elite LinkedIn Content & B2B Strategy Specialist.\n"
        "Generate a 30-day LinkedIn Content Calendar. You must format the response as a JSON object matching the requested schema.\n"
        "Ensure all 30 days are generated completely without placeholders or truncation."
    )

    user_prompt = f"""
    Create a 30-day LinkedIn posting schedule for a campaign in the '{industry}' industry.
    - Campaign Goal: {campaign_goal}
    - Target Audience: {target_audience}

    Define 3 distinct content pillars (e.g. Thought Leadership, Case Studies, Industry Insights).
    Generate 30 distinct, detailed posts, one for each day.
    
    Each post in the schedule must have:
    - day (int, 1-30)
    - pillar (string, matching one of the 3 pillars)
    - topic (string)
    - hook_concept (string, explaining the hook idea)
    - generated_post (string, the actual body of the post. Keep it engaging, professional, with natural paragraph breaks, and direct CTA)
    - hashtags (list of 2-3 relevant strings)

    Return ONLY a JSON object matching this schema:
    {{
        "pillars": ["Pillar A", "Pillar B", "Pillar C"],
        "schedule": [
            {{
                "day": 1,
                "pillar": "Pillar A",
                "topic": "Topic Name",
                "hook_concept": "Hook Concept",
                "generated_post": "Detailed body text of the LinkedIn post here...",
                "hashtags": ["hashtag1", "hashtag2"]
            }},
            ...
        ]
    }}
    Ensure the JSON is completely valid and parses correctly. Do not truncate the schedule; output all 30 days.
    """

    try:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        raw_output = groq_inference(messages, temperature=0.7, max_tokens=4096)
        parsed = _extract_json(raw_output)
    except Exception as exc:
        logger.warning(f"Could not parse LinkedIn calendar: {exc}")
        # Fallback empty structure
        parsed = {
            "pillars": ["Industry Trends", "Growth Hack", "Company News"],
            "schedule": [
                {
                    "day": i,
                    "pillar": "Industry Trends",
                    "topic": f"Topic for Day {i}",
                    "hook_concept": "Catchy industry hook",
                    "generated_post": f"Did you know that in the {industry} space, key shifts are happening? Let's discuss.",
                    "hashtags": ["trends", industry.lower().replace(" ", "")]
                } for i in range(1, 31)
            ]
        }

    db = await get_database()
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    calendar_id = str(uuid.uuid4())
    
    calendar_doc = {
        "id": calendar_id,
        "user_id": user_id,
        "campaign_id": campaign_id,
        "campaign_goal": campaign_goal,
        "target_audience": target_audience,
        "industry": industry,
        "pillars": parsed.get("pillars", []),
        "schedule": parsed.get("schedule", []),
        "created_at": now
    }

    await db.content.insert_one(calendar_doc)
    calendar_doc.pop("_id", None)
    return calendar_doc



def generate_meeting_summary(
    meeting_notes: str,
    lead_data: dict,
) -> dict[str, Any]:
    """
    Generate a structured meeting summary from notes framework-freely.

    Args:
        meeting_notes: Raw notes from the meeting.
        lead_data: Basic lead information.

    Returns:
        Structured summary as a dictionary.
    """
    lead_name = lead_data.get("name", "Unknown")

    logger.info(f"Generating framework-free meeting summary for: {lead_name}")

    system_prompt = (
        "You are an expert meeting analyst and content strategist. "
        "You excel at summarizing meetings and identifying actionable follow-up tasks "
        "to keep deals moving forward."
    )

    user_prompt = f"""
Analyze the following meeting notes from a conversation with {lead_name}
and produce a structured summary with key takeaways and next steps.

**Meeting Notes:**
{meeting_notes}

**Lead Info:**
- Name: {lead_name}
- Company: {lead_data.get('company', 'Unknown')}
- Role: {lead_data.get('role', 'Unknown')}

Return a JSON object with:
{{
    "executive_summary": "3-5 sentences summary",
    "key_points": ["Key topic 1", "Key topic 2"],
    "action_items": [{{"task": "Next step description", "owner": "Owner name", "due_date": "YYYY-MM-DD"}}],
    "follow_up_timing": "timeline",
    "sentiment": "positive|neutral|mixed",
    "deal_velocity": "accelerated|stable|slowed",
    "suggested_next_steps": ["step 1", "step 2"]
}}
"""

    try:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        raw_output = groq_inference(messages, temperature=0.3)
        parsed = _extract_json(raw_output)
        return parsed
    except Exception as exc:
        logger.warning(f"Could not parse meeting summary framework-freely: {exc}")
        return {
            "executive_summary": "Meeting notes analysis fallback summary.",
            "key_points": [],
            "action_items": [],
            "follow_up_timing": "unknown",
            "sentiment": "unknown",
            "deal_velocity": "unknown",
            "suggested_next_steps": [],
        }


def _extract_json(text: str) -> dict:
    """Extract and parse the first JSON object found in a text string."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    code_block_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if code_block_match:
        block = code_block_match.group(1).strip()
        try:
            return json.loads(block)
        except json.JSONDecodeError:
            pass

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