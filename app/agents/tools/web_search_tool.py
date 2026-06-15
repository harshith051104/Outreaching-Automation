"""
Web Search Tool for the Research Agent.

Uses httpx to perform web searches and Groq to synthesize research
findings into structured intelligence about companies and leads.
"""

import json
import logging
from typing import Type
import httpx
from groq import Groq
from pydantic import BaseModel, Field
from app.config.settings import settings

logger = logging.getLogger(__name__)


class WebSearchInput(BaseModel):
    """Input schema for the Web Research Tool."""
    query: str = Field(
        ...,
        description="The search query to research. Can be a company name, person name, "
        "industry topic, or any business-related research query.",
    )


class WebSearchTool:
    """
    Custom tool for web-based research on companies and people.

    Attempts to fetch real data via httpx from public sources, then uses
    Groq to synthesize and structure the findings into actionable
    business intelligence.
    """

    def __init__(self):
        self.name = "Web Research Tool"
        self.description = (
            "Research a company or person online to gather relevant information "
            "including company details, recent news, leadership, technologies used, "
            "funding history, and potential pain points."
        )

    def run(self, query: str) -> str:
        return self._run(query)

    def _run(self, query: str) -> str:
        """
        Execute web research for the given query.

        Fetches publicly available information and synthesizes it into
        a structured research report using Groq.
        """
        gathered_info = self._fetch_web_data(query)
        research_report = self._synthesize_research(query, gathered_info)
        return research_report

    def _fetch_web_data(self, query: str) -> str:
        """Attempt to fetch basic web data about the query subject."""
        snippets: list[str] = []

        urls_to_try = [
            f"https://api.duckduckgo.com/?q={query}&format=json&no_html=1&skip_disambig=1",
        ]

        for url in urls_to_try:
            try:
                with httpx.Client(timeout=10.0, follow_redirects=True) as client:
                    response = client.get(url)
                    if response.status_code == 200:
                        data = response.json()
                        abstract = data.get("Abstract", "")
                        if abstract:
                            snippets.append(f"Summary: {abstract}")

                        heading = data.get("Heading", "")
                        if heading:
                            snippets.append(f"Heading: {heading}")

                        related_topics = data.get("RelatedTopics", [])
                        for topic in related_topics[:5]:
                            text = topic.get("Text", "")
                            if text:
                                snippets.append(f"Related: {text}")

            except (httpx.HTTPError, json.JSONDecodeError, Exception) as e:
                logger.debug(f"Web fetch failed for {url}: {e}")
                continue

        if not snippets:
            snippets.append(
                f"No direct web data retrieved for '{query}'. "
                "Synthesizing research based on general knowledge."
            )

        return "\n".join(snippets)

    def _synthesize_research(self, query: str, gathered_info: str) -> str:
        """Use Groq to synthesize gathered data into a structured research report."""
        try:
            client = Groq(api_key=settings.GROQ_API_KEY)
            response = client.chat.completions.create(
                model=settings.GROQ_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an elite business intelligence researcher. "
                            "Synthesize the provided information into a comprehensive, "
                            "structured research report. If limited data is available, "
                            "use your knowledge to provide relevant business context. "
                            "Always be factual and indicate confidence levels."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Research Query: {query}\n\n"
                            f"Gathered Information:\n{gathered_info}\n\n"
                            "Please provide a structured research report with these sections:\n"
                            "1. **Company Overview**: What the company does, size, industry\n"
                            "2. **Recent Developments**: News, product launches, funding\n"
                            "3. **Leadership**: Key people and their backgrounds\n"
                            "4. **Technology Stack**: Known technologies and tools used\n"
                            "5. **Pain Points**: Likely challenges based on industry/size\n"
                            "6. **Growth Signals**: Indicators of growth or change\n"
                            "7. **Outreach Angles**: Recommended personalization hooks\n\n"
                            "Format the output as a clean JSON object with these keys: "
                            "company_overview, recent_developments, leadership, "
                            "technology_stack, pain_points, growth_signals, outreach_angles"
                        ),
                    },
                ],
                temperature=0.3,
                max_tokens=2000,
            )
            return response.choices[0].message.content or "No research data generated."
        except Exception as e:
            logger.error(f"Groq synthesis failed: {e}")
            return json.dumps(
                {
                    "company_overview": f"Research target: {query}",
                    "recent_developments": "Unable to retrieve — API error occurred.",
                    "leadership": "Data unavailable.",
                    "technology_stack": "Data unavailable.",
                    "pain_points": "Requires manual research.",
                    "growth_signals": "Data unavailable.",
                    "outreach_angles": "Use generic personalization approach.",
                    "error": str(e),
                }
            )