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

    def _get_headers(self, api_key: str | None = None) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
        }
        key = api_key if api_key is not None else self.api_key
        if key:
            headers["Authorization"] = f"Bearer {key}"
            headers["X-Api-Key"] = key
        return headers

    async def search_leads(
        self,
        job_titles: Optional[List[str]] = None,
        locations: Optional[List[str]] = None,
        industry: Optional[str] = None,
        limit: int = 10,
        user_id: str | None = None,
    ) -> List[Dict[str, Any]]:
        """Search for leads on Apollo."""
        api_key = self.api_key
        if user_id:
            from app.services.integrations_service import get_api_key
            api_key = await get_api_key(user_id, "apollo", self.api_key)
            if api_key:
                api_key = api_key.strip('"').strip("'")

        if not api_key:
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
                if api_key:
                    payload["api_key"] = api_key

                response = await client.post(
                    f"{self.base_url}/mixed_people/search",
                    headers=self._get_headers(api_key=api_key),
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

    async def enrich_company(self, domain: str, user_id: str | None = None) -> Dict[str, Any]:
        """Enrich company data from Apollo."""
        api_key = self.api_key
        if user_id:
            from app.services.integrations_service import get_api_key
            api_key = await get_api_key(user_id, "apollo", self.api_key)
            if api_key:
                api_key = api_key.strip('"').strip("'")

        if not api_key:
            return {}

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                params = {"domain": domain}
                if api_key:
                    params["api_key"] = api_key
                response = await client.get(
                    f"{self.base_url}/organizations/enrich",
                    headers=self._get_headers(api_key=api_key),
                    params=params,
                )

                if response.status_code == 200:
                    return response.json()
                return {}
        except Exception as e:
            logger.error(f"Apollo enrich error: {e}")
            return {}