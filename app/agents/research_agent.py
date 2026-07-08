"""
Research Agent — Conducts thorough research on leads, companies, and industries.

Uses the WebSearchTool to gather intelligence and produces structured
research reports that downstream agents consume for personalization.
"""

import json
import logging
import re
from typing import Any

from app.agents.tools.web_search_tool import WebSearchTool
from app.config.groq_config import groq_inference
from app.prompts.research_prompts import COMPANY_RESEARCH_PROMPT, LEAD_RESEARCH_PROMPT

logger = logging.getLogger(__name__)


def research_lead(lead_data: dict) -> dict[str, Any]:
    """
    Run the full research pipeline for a single lead framework-freely.

    Args:
        lead_data: Dictionary with lead information.

    Returns:
        Parsed research report as a dictionary.
    """
    lead_name = lead_data.get("name", "Unknown")
    company = lead_data.get("company", "Unknown")
    role = lead_data.get("role", "Unknown")
    website = lead_data.get("website", "N/A")
    industry = lead_data.get("industry", "N/A")
    linkedin_url = lead_data.get("linkedin_url", "N/A")

    logger.info(f"Starting framework-free research for lead: {lead_name}")

    # Use WebSearchTool to gather public web data
    search_tool = WebSearchTool()
    search_query = f"{lead_name} {role} {company}"
    web_data = search_tool._fetch_web_data(search_query)

    # Build prompt for LLM synthesis
    system_prompt = (
        "You are an elite business intelligence researcher with 15 years of experience in B2B sales research. "
        "You excel at finding key information about companies, their leadership, recent news, pain points, and growth opportunities. "
        "Your research enables sales teams to craft deeply personalized outreach that resonates with each prospect. "
        "You always provide structured, actionable intelligence — never vague summaries."
    )

    user_prompt = f"""
Research the following lead and their company to gather actionable intelligence
for a personalized cold outreach campaign.

**Lead Information:**
- Name: {lead_name}
- Role: {role}
- Company: {company}
- Website: {website}
- Industry: {industry}
- LinkedIn: {linkedin_url}

**Gathered Web Research Snippets:**
{web_data}

**Research Objectives:**
1. **Company Research**: Understand what {company} does, their market position, recent news (funding, product launches, expansions), company size, and technology stack.
2. **Lead Research**: Understand {lead_name}'s professional background, their responsibilities as {role}, any public talks/articles, and their likely priorities and pain points.
3. **Industry Context**: Identify relevant industry trends, challenges, and opportunities affecting {company} and {lead_name}'s role.
4. **Pain Points**: Infer the top 3-5 pain points that {lead_name} likely faces in their role at {company}, based on company size, industry, and recent events.
5. **Outreach Angles**: Suggest 2-3 specific personalization hooks that could be used to start a meaningful conversation.

Return your final output strictly as a JSON object matching this structure:
{{
    "lead": {{
        "name": "{lead_name}",
        "role": "{role}",
        "background": "Brief professional background",
        "key_achievements": ["Achievement 1", "Achievement 2"],
        "likely_priorities": ["Priority 1", "Priority 2"]
    }},
    "company": {{
        "name": "{company}",
        "description": "Company description",
        "industry": "{industry}",
        "size_estimate": "Estimated size",
        "recent_news": ["News item 1", "News item 2"],
        "technology_stack": ["Tech 1", "Tech 2"],
        "competitors": ["Competitor 1", "Competitor 2"]
    }},
    "pain_points": [
        {{"pain_point": "Specific challenge description", "evidence": "Why they face this", "confidence": "high/medium/low"}}
    ],
    "outreach_angles": [
        {{"angle": "Specific personalization hook angle", "hook": "Personalized opening line proposal", "relevance": "Why this hook works"}}
    ],
    "industry_trends": ["Trend 1", "Trend 2"],
    "research_confidence": "high/medium/low"
}}
"""

    try:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        raw_output = groq_inference(messages, temperature=0.3)
        parsed = _extract_json(raw_output)
        logger.info("Research completed framework-freely — JSON parsed successfully.")
        return parsed
    except Exception as exc:
        logger.warning(f"Could not synthesize research output as JSON: {exc}; returning raw/placeholder format.")
        return {
            "lead": {
                "name": lead_name,
                "role": role,
                "background": "Information gathered during search",
                "key_achievements": [],
                "likely_priorities": []
            },
            "company": {
                "name": company,
                "description": f"Target company: {company}",
                "industry": industry,
                "size_estimate": "Unknown",
                "recent_news": [],
                "technology_stack": [],
                "competitors": []
            },
            "pain_points": [
                {"pain_point": f"Managing B2B operations as {role}", "evidence": "Industry role constraints", "confidence": "medium"}
            ],
            "outreach_angles": [
                {"angle": "Direct Value Prop", "hook": f"Hi {lead_name}, noticed your work at {company}...", "relevance": "Direct outreach"}
            ],
            "industry_trends": [],
            "research_confidence": "low"
        }


def _extract_json(text: str) -> dict:
    """Extract and parse the first JSON object found in a text string."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find JSON inside ``` code blocks (with or without json tag)
    code_block_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if code_block_match:
        block = code_block_match.group(1).strip()
        try:
            return json.loads(block)
        except json.JSONDecodeError:
            pass

    # Fallback: find first { and match braces to find the complete JSON object
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