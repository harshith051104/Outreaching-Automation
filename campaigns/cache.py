"""
AI Cache — caches AI-generated values by campaign_id + investor_focus + template_version.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class AICache:
    """Cache for AI-generated placeholder values."""

    def __init__(self, db: Any = None):
        self._db = db

    def _make_key(self, campaign_id: str, investor_focus: str, template_version: str = "v1") -> str:
        return f"{campaign_id}:{investor_focus}:{template_version}"

    async def get(
        self,
        campaign_id: str,
        investor_focus: str,
        template_version: str = "v1",
    ) -> Optional[Dict[str, str]]:
        """Load cached AI values."""
        if not self._db:
            return None
        key = self._make_key(campaign_id, investor_focus, template_version)
        doc = await self._db.ai_placeholder_cache.find_one({"cache_key": key})
        if doc:
            return doc.get("values", {})
        return None

    async def set(
        self,
        campaign_id: str,
        investor_focus: str,
        values: Dict[str, str],
        template_version: str = "v1",
    ) -> None:
        """Save AI values to cache."""
        if not self._db:
            return
        key = self._make_key(campaign_id, investor_focus, template_version)
        await self._db.ai_placeholder_cache.update_one(
            {"cache_key": key},
            {"$set": {"values": values, "updated_at": datetime.now(timezone.utc)}},
            upsert=True,
        )

    async def clear(
        self,
        campaign_id: str,
        lead_id: str,
    ) -> None:
        """Clear cached values for a lead+campaign."""
        if not self._db:
            return
        # Clear by legacy key format too
        legacy_key = f"{campaign_id}:{lead_id}"
        await self._db.ai_placeholder_cache.delete_one({"cache_key": legacy_key})

    async def clear_campaign(self, campaign_id: str) -> None:
        """Clear all cached values for a campaign."""
        if not self._db:
            return
        import re
        await self._db.ai_placeholder_cache.delete_many(
            {"cache_key": {"$regex": f"^{re.escape(campaign_id)}:"}}
        )
