"""
Engagement scoring and campaign analytics.
"""

from __future__ import annotations

from typing import Any, Dict

from email_delivery.persistence import EmailPersistence
from email_delivery.config import email_config


class EngagementScorer:
    """Compute lead engagement scores from tracking events."""

    def __init__(self, persistence: EmailPersistence | None = None):
        self.persistence = persistence or EmailPersistence()

    async def score_lead(self, lead_id: str) -> float:
        from app.config.mongodb_config import get_database
        db = await get_database()
        pipeline = [
            {"$match": {"lead_id": lead_id}},
            {"$group": {"_id": "$event_type", "count": {"$sum": 1}}},
        ]
        results = await db.tracking_events.aggregate(pipeline).to_list(length=10)
        score = 0.0
        weights = {
            "open": email_config.open_tracking_weight,
            "click": email_config.click_tracking_weight,
            "reply": email_config.reply_tracking_weight,
            "attachment_view": email_config.attachment_tracking_weight,
        }
        for r in results:
            score += r["count"] * weights.get(r["_id"], 0.0)
        return score

    async def score_campaign(self, campaign_id: str) -> Dict[str, Any]:
        stats = await self.persistence.get_tracking_stats(campaign_id)
        total_sent = await self._count_sent(campaign_id)
        open_rate = (stats["unique_opens"] / total_sent * 100) if total_sent else 0.0
        click_rate = (stats["unique_clicks"] / total_sent * 100) if total_sent else 0.0
        reply_rate = (stats["replies"] / total_sent * 100) if total_sent else 0.0
        return {
            "campaign_id": campaign_id,
            "total_sent": total_sent,
            "opens": stats["opens"],
            "unique_opens": stats["unique_opens"],
            "open_rate": round(open_rate, 2),
            "clicks": stats["clicks"],
            "unique_clicks": stats["unique_clicks"],
            "click_rate": round(click_rate, 2),
            "replies": stats["replies"],
            "reply_rate": round(reply_rate, 2),
        }

    async def _count_sent(self, campaign_id: str) -> int:
        from app.config.mongodb_config import get_database
        db = await get_database()
        return await db.emails.count_documents({
            "campaign_id": campaign_id,
            "status": {"$in": ["sent", "delivered", "opened", "clicked", "replied"]},
        })


class CampaignAnalytics:
    """Wrapper for campaign-level analytics aggregation."""

    def __init__(self, persistence: EmailPersistence | None = None):
        self.persistence = persistence or EmailPersistence()
        self.scorer = EngagementScorer(persistence)

    async def get_summary(self, campaign_id: str) -> Dict[str, Any]:
        return await self.scorer.score_campaign(campaign_id)

    async def get_events(self, campaign_id: str, limit: int = 500) -> list:
        return await self.persistence.get_tracking_events(campaign_id=campaign_id, limit=limit)
