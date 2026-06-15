"""
Tavily Search API service for web research.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

HAS_TAVILY = True

try:
    import httpx
    from app.config.settings import settings
except ImportError:
    HAS_TAVILY = False


class TavilyService:
    """Service for web search and lead discovery via Tavily."""

    def __init__(self):
        self.api_key = settings.TAVILY_API_KEY
        self.base_url = "https://api.tavily.com"

    async def search(self, query: str, max_results: int = 4) -> List[Dict[str, Any]]:
        """Search the web using Tavily."""
        if not self.api_key:
            logger.warning("Tavily API key not set")
            return []

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/search",
                    json={
                        "api_key": self.api_key,
                        "query": query,
                        "max_results": max_results,
                        "include_answer": True,
                        "include_raw_content": False,
                    },
                )

                if response.status_code == 200:
                    data = response.json()
                    results = data.get("results", [])
                    return [
                        {
                            "url": r.get("url", ""),
                            "content": r.get("content", ""),
                            "score": r.get("score", 0),
                        }
                        for r in results
                    ]
                return []
        except Exception as e:
            logger.error(f"Tavily search error: {e}")
            return []

    async def discover_leads(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Discover leads from web search results."""
        results = await self.search(query, max_results=limit)

        leads = []
        import re
        from urllib.parse import urlparse
        for r in results:
            content = r.get("content", "")
            url = r.get("url", "")

            # Regex search for emails and linkedin profile URLs in content
            email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', content)
            email = email_match.group(0) if email_match else ""

            linkedin_match = re.search(r'https?://(?:www\.)?linkedin\.com/(?:in|company)/[a-zA-Z0-9_-]+', content)
            linkedin = linkedin_match.group(0) if linkedin_match else ""

            if "linkedin.com" in url.lower():
                linkedin = url

            # Extract company name from domain if possible
            company = ""
            if url:
                try:
                    parsed = urlparse(url)
                    domain = parsed.netloc
                    if domain:
                        if domain.startswith("www."):
                            domain = domain[4:]
                        company = domain.split(".")[0].title()
                        
                        # Fallback constructed email if we have no email or linkedin
                        if not email and not linkedin:
                            if domain not in ["linkedin.com", "google.com", "facebook.com", "twitter.com", "youtube.com", "github.com", "wikipedia.org"]:
                                email = f"contact@{domain}"
                except Exception:
                    pass

            if email or linkedin:
                lead = {
                    "name": "Contact",
                    "title": "Professional",
                    "company": company,
                    "email": email,
                    "linkedin": linkedin,
                    "website": url,
                }
                leads.append(lead)

        return leads

    async def get_company_info(self, company_name: str) -> Dict[str, Any]:
        """Get company information from Tavily."""
        results = await self.search(f"{company_name} company about", max_results=3)

        if results:
            return {
                "content": results[0].get("content", ""),
                "url": results[0].get("url", ""),
            }
        return {}