"""
Apollo.io API service for lead search.
"""

import logging
import asyncio
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

HAS_APOLLO = True

try:
    import httpx
    from app.config.settings import settings
except ImportError:
    HAS_APOLLO = False


class ApolloService:
    """Service for searching leads on Apollo.io."""

    def __init__(self):
        self.api_key = settings.APOLLO_API_KEY.strip('"').strip("'") if settings.APOLLO_API_KEY else ""
        self.base_url = "https://api.apollo.io/api/v1"

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
            headers["X-Api-Key"] = self.api_key
        return headers

    async def search_leads(
        self,
        job_titles: Optional[List[str]] = None,
        locations: Optional[List[str]] = None,
        industry: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Search for leads on Apollo."""
        if not self.api_key:
            logger.warning("Apollo API key not set")
            return []

        query_parts = []
        if job_titles:
            query_parts.extend(job_titles)
        if locations:
            query_parts.extend(locations)
        if industry:
            query_parts.append(industry)

        query = " ".join(query_parts) if query_parts else ""

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                payload = {
                    "query": query,
                    "page_size": limit,
                    "person_titles": job_titles,
                    "locations": locations,
                }
                if self.api_key:
                    payload["api_key"] = self.api_key

                response = await client.post(
                    f"{self.base_url}/mixed_people/search",
                    headers=self._get_headers(),
                    json=payload,
                )

                if response.status_code == 200:
                    data = response.json()
                    people = data.get("people", [])
                    return [
                        {
                            "name": p.get("name", ""),
                            "title": p.get("title", ""),
                            "company": p.get("organization", {}).get("name", ""),
                            "email": p.get("email", ""),
                            "linkedin": p.get("linkedin_url", ""),
                            "website": p.get("organization", {}).get("website", ""),
                        }
                        for p in people
                        if p.get("name")
                    ]
                else:
                    logger.warning(f"Apollo search failed: {response.status_code}")
                    return []
        except Exception as e:
            logger.error(f"Apollo search error: {e}")
            return []

    async def enrich_company(self, domain: str) -> Dict[str, Any]:
        """Enrich company data from Apollo."""
        if not self.api_key:
            return {}

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                params = {"domain": domain}
                if self.api_key:
                    params["api_key"] = self.api_key
                response = await client.get(
                    f"{self.base_url}/organizations/enrich",
                    headers=self._get_headers(),
                    params=params,
                )

                if response.status_code == 200:
                    return response.json()
                return {}
        except Exception as e:
            logger.error(f"Apollo enrich error: {e}")
            return {}