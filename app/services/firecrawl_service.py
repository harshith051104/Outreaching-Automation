"""
Firecrawl web scraping service.
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

HAS_FIRECRAWL = True

try:
    import httpx
    from app.config.settings import settings
except ImportError:
    HAS_FIRECRAWL = False


class FirecrawlService:
    """Service for scraping web pages using Firecrawl."""

    def __init__(self):
        self.api_key = settings.FIRECRAWL_API_KEY
        self.base_url = "https://api.firecrawl.dev"

    async def scrape_url(
        self,
        url: str,
        max_length: int = 4000,
        user_id: str | None = None,
    ) -> Optional[str]:
        """Scrape a URL and return markdown content."""
        api_key = self.api_key
        if user_id:
            from app.services.integrations_service import get_api_key
            api_key = await get_api_key(user_id, "firecrawl", self.api_key)

        if not api_key:
            logger.warning("Firecrawl API key not set")
            return None

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.base_url}/v0/scrape",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "url": url,
                        "formats": ["markdown"],
                        "onlyMainContent": True,
                    },
                )

                if response.status_code == 200:
                    data = response.json()
                    markdown = data.get("data", {}).get("markdown", "")
                    return markdown[:max_length] if markdown else None
                else:
                    logger.warning(f"Firecrawl scrape failed: {response.status_code}")
                    return None
        except Exception as e:
            logger.error(f"Firecrawl scrape error: {e}")
            return None

    async def crawl(
        self,
        urls: list,
        max_depth: int = 1,
        user_id: str | None = None,
    ) -> list:
        """Crawl multiple URLs."""
        api_key = self.api_key
        if user_id:
            from app.services.integrations_service import get_api_key
            api_key = await get_api_key(user_id, "firecrawl", self.api_key)

        if not api_key:
            return []

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.base_url}/v0/crawl",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "urls": urls,
                        "maxDepth": max_depth,
                        "formats": ["markdown"],
                    },
                )

                if response.status_code == 200:
                    data = response.json()
                    return data.get("data", [])
                return []
        except Exception as e:
            logger.error(f"Firecrawl crawl error: {e}")
            return []