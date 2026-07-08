"""
Personalization Agent — Creates deeply personalized email elements
based on lead research data.

Operates purely on the research intelligence provided; no external tools
required. Generates personalized openers, pain-point mappings, custom
value propositions, and icebreaker ideas.
"""

import json
import logging
import re
from typing import Any

from app.config.groq_config import groq_inference

logger = logging.getLogger(__name__)


def personalize_for_lead(
    lead_data: dict, research_data: dict
) -> dict[str, Any]:
    """
    Run the personalization pipeline for a lead framework-freely.

    Args:
        lead_data: Basic lead information.
        research_data: Research intelligence from the research agent.

    Returns:
        Personalization data as a dictionary.
    """
    lead_name = lead_data.get("name", "Unknown")
    company = lead_data.get("company", "Unknown")
    role = lead_data.get("role", "Unknown")

    research_summary = json.dumps(research_data, indent=2, default=str)

    logger.info(f"Generating framework-free personalization for lead: {lead_name}")

    system_prompt = (
        "You are an Email Personalization Expert. You are a master copywriter who has spent 12 years specializing in B2B email personalization. "
        "You understand that true personalization goes far beyond inserting a first name — it's about demonstrating genuine understanding "
        "of a prospect's world, challenges, and aspirations. You craft openers that make recipients think 'this person actually gets me' "
        "and value propositions that speak directly to their specific situation."
    )

    user_prompt = f"""
Using the research intelligence below, create deeply personalized email
elements for reaching out to {lead_name} ({role} at {company}).

**Lead Information:**
- Name: {lead_name}
- Role: {role}
- Company: {company}
- Email: {lead_data.get("email", "N/A")}

**Research Intelligence:**
{research_summary}

**Your Objectives:**

1. **Personalized Opener (2-3 sentences):**
   Write an opening that immediately shows you've done your homework.
   Reference something specific — a recent company milestone, an article
   they wrote, a product launch, or a challenge their industry faces.
   Make it feel natural, not stalker-ish.

2. **Pain Point Mapping (top 3):**
   Based on the research, identify the 3 most relevant pain points for
   {lead_name} in their role as {role}. For each, explain WHY it matters
   to them specifically (not generically) and how it connects to their
   current situation.

3. **Custom Value Proposition:**
   Craft a 1-2 sentence value proposition that directly addresses their
   most pressing pain point. Avoid generic statements — tie the value
   to their specific company, industry, or situation.

4. **Icebreaker Ideas (2-3):**
   Generate conversation starters that could work as opening lines or
   P.S. lines. These should be warm, genuine, and based on real research
   findings — shared interests, mutual connections, industry opinions.

**Quality Standards:**
- Every element must reference specific, verifiable information
- Avoid clichés like "I hope this email finds you well"
- Write at a 7th-grade reading level for clarity
- Each element should feel human-written, not template-generated

Return your output strictly as a JSON object matching this structure:
{{
    "personalized_opener": "A 2-3 sentence personalized opening...",
    "pain_points": [
        {{
            "pain_point": "Specific challenge description",
            "relevance": "Why this matters to them specifically",
            "intensity": "high/medium/low"
        }}
    ],
    "value_proposition": "A targeted 1-2 sentence value prop...",
    "icebreakers": [
        "Icebreaker idea 1...",
        "Icebreaker idea 2..."
    ],
    "personalization_confidence": "high/medium/low",
    "recommended_tone": "professional/casual/friendly"
}}
"""

    try:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        raw_output = groq_inference(messages, temperature=0.5)
        parsed = _extract_json(raw_output)
        logger.info("Personalization completed framework-freely — JSON parsed successfully.")
        return parsed
    except Exception as exc:
        logger.warning(f"Could not synthesize personalization output as JSON: {exc}")
        return {
            "personalized_opener": f"Hi {lead_name}, was following the developments at {company} and wanted to reach out.",
            "pain_points": [
                {
                    "pain_point": "Scaling operations efficiently",
                    "relevance": "Relevant challenge for B2B executives",
                    "intensity": "medium"
                }
            ],
            "value_proposition": f"We help companies like {company} streamline their B2B processes.",
            "icebreakers": [
                f"Congrats on the growth at {company}!"
            ],
            "personalization_confidence": "low",
            "recommended_tone": "professional"
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