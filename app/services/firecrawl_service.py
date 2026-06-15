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

    async def scrape_url(self, url: str, max_length: int = 4000) -> Optional[str]:
        """Scrape a URL and return markdown content."""
        if not self.api_key:
            logger.warning("Firecrawl API key not set")
            return None

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.base_url}/v0/scrape",
                    headers={"Authorization": f"Bearer {self.api_key}"},
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

    async def crawl(self, urls: list, max_depth: int = 1) -> list:
        """Crawl multiple URLs."""
        if not self.api_key:
            return []

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.base_url}/v0/crawl",
                    headers={"Authorization": f"Bearer {self.api_key}"},
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