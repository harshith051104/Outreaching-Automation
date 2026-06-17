"""
Analytics tasks and service.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any
from app.config.redis_config import celery_app

from app.config.mongodb_config import get_database
from app.utils.id_generator import generate_id

logger = logging.getLogger(__name__)


async def update_campaign_analytics(campaign_id: str) -> None:
    """Recalculate and persist analytics for a campaign."""
    analytics = await _compute_analytics(campaign_id)
    db = await get_database()
    now = datetime.now(timezone.utc)

    existing = await db.analytics.find_one({"campaign_id": campaign_id})
    if existing:
        await db.analytics.update_one(
            {"campaign_id": campaign_id},
            {"$set": {**analytics, "updated_at": now}},
        )
    else:
        analytics["id"] = generate_id()
        analytics["created_at"] = now
        analytics["updated_at"] = now
        await db.analytics.insert_one(analytics)


async def _compute_analytics(campaign_id: str) -> Dict[str, Any]:
    """Compute analytics from emails and tracking events."""
    db = await get_database()

    emails_sent = await db.emails.count_documents({"campaign_id": campaign_id, "status": "sent"})
    emails_failed = await db.emails.count_documents({"campaign_id": campaign_id, "status": "failed"})

    pipeline = [
        {"$match": {"campaign_id": campaign_id}},
        {"$group": {"_id": "$event_type", "count": {"$sum": 1}, "unique_emails": {"$addToSet": "$email_id"}}},
    ]
    agg = await db.tracking_events.aggregate(pipeline).to_list(length=10)

    opens = clicks = replies = unique_opens = unique_clicks = 0
    for r in agg:
        if r["_id"] == "open":
            opens = r["count"]
            unique_opens = len(r["unique_emails"])
        elif r["_id"] == "click":
            clicks = r["count"]
            unique_clicks = len(r["unique_emails"])
        elif r["_id"] == "reply":
            replies = r["count"]

    open_rate = (unique_opens / emails_sent * 100) if emails_sent > 0 else 0.0
    click_rate = (unique_clicks / emails_sent * 100) if emails_sent > 0 else 0.0
    reply_rate = (replies / emails_sent * 100) if emails_sent > 0 else 0.0

    return {
        "campaign_id": campaign_id,
        "emails_sent": emails_sent,
        "emails_failed": emails_failed,
        "total_opens": opens,
        "unique_opens": unique_opens,
        "total_clicks": clicks,
        "unique_clicks": unique_clicks,
        "total_replies": replies,
        "open_rate": round(open_rate, 2),
        "click_rate": round(click_rate, 2),
        "reply_rate": round(reply_rate, 2),
    }


async def get_campaign_analytics(campaign_id: str, user_id: str) -> Dict:
    """Get analytics for a campaign."""
    db = await get_database()

    campaign = await db.campaigns.find_one({"id": campaign_id, "user_id": user_id}, {"_id": 0})
    if not campaign:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found.")

    analytics = await db.analytics.find_one({"campaign_id": campaign_id}, {"_id": 0})
    if analytics:
        return analytics

    return await _compute_analytics(campaign_id)


async def get_dashboard_stats(user_id: str) -> Dict:
    """Aggregate stats across all user campaigns."""
    db = await get_database()

    total_campaigns = await db.campaigns.count_documents({"user_id": user_id, "status": {"$ne": "deleted"}})
    active_campaigns = await db.campaigns.count_documents({"user_id": user_id, "status": "active"})
    total_leads = await db.leads.count_documents({"user_id": user_id})

    campaign_cursor = db.campaigns.find({"user_id": user_id, "status": {"$ne": "deleted"}}, {"id": 1, "_id": 0})
    campaign_ids = [c["id"] for c in await campaign_cursor.to_list(length=500)]

    total_emails_sent = await db.emails.count_documents({"campaign_id": {"$in": campaign_ids}, "status": "sent"})

    pipeline = [
        {"$match": {"campaign_id": {"$in": campaign_ids}}},
        {"$group": {"_id": "$event_type", "count": {"$sum": 1}}},
    ]
    agg_results = await db.tracking_events.aggregate(pipeline).to_list(length=10)

    event_counts = {r["_id"]: r["count"] for r in agg_results}

    total_opens = event_counts.get("open", 0)
    total_clicks = event_counts.get("click", 0)
    total_replies = event_counts.get("reply", 0)

    open_rate = (total_opens / total_emails_sent * 100) if total_emails_sent > 0 else 0.0
    click_rate = (total_clicks / total_emails_sent * 100) if total_emails_sent > 0 else 0.0
    reply_rate = (total_replies / total_emails_sent * 100) if total_emails_sent > 0 else 0.0

    return {
        "total_campaigns": total_campaigns,
        "active_campaigns": active_campaigns,
        "total_leads": total_leads,
        "total_emails_sent": total_emails_sent,
        "total_opens": total_opens,
        "total_clicks": total_clicks,
        "total_replies": total_replies,
        "open_rate": round(open_rate, 2),
        "click_rate": round(click_rate, 2),
        "reply_rate": round(reply_rate, 2),
    }


async def get_daily_stats(campaign_id: str, days: int = 30) -> List[Dict]:
    """Get daily breakdowns for the past N days."""
    db = await get_database()
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    pipeline = [
        {"$match": {"campaign_id": campaign_id, "timestamp": {"$gte": cutoff}}},
        {"$group": {"_id": {"date": {"$dateToString": {"format": "%Y-%m-%d", "date": "$timestamp"}}, "event_type": "$event_type"}, "count": {"$sum": 1}}},
        {"$sort": {"_id.date": 1}},
    ]

    results = await db.tracking_events.aggregate(pipeline).to_list(length=500)

    daily_map = {}
    for r in results:
        date_str = r["_id"]["date"]
        event_type = r["_id"]["event_type"]
        if date_str not in daily_map:
            daily_map[date_str] = {"date": date_str, "opens": 0, "clicks": 0, "replies": 0}
        key_mapping = {"open": "opens", "click": "clicks", "reply": "replies"}
        plural_key = key_mapping.get(event_type)
        if plural_key:
            daily_map[date_str][plural_key] = r["count"]

    daily_list = []
    for i in range(days):
        d = (datetime.now(timezone.utc) - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d")
        entry = daily_map.get(d, {"date": d, "opens": 0, "clicks": 0, "replies": 0})
        entry.setdefault("emails_sent", 0)
        daily_list.append(entry)

    return daily_list


async def refresh_all_campaign_analytics() -> dict:
    """Refresh analytics for all active campaigns."""
    db = await get_database()

    cursor = db.campaigns.find({"status": {"$in": ["active", "paused", "completed"]}}, {"id": 1})
    campaigns = await cursor.to_list(length=500)

    if not campaigns:
        return {"status": "ok", "campaigns_updated": 0}

    results = []
    for campaign in campaigns:
        try:
            await update_campaign_analytics(campaign["id"])
            results.append({"campaign_id": campaign["id"], "status": "updated"})
        except Exception as exc:
            results.append({"campaign_id": campaign["id"], "status": "error", "error": str(exc)})

    return {
        "status": "processed",
        "campaigns_updated": len([r for r in results if r["status"] == "updated"]),
        "errors": len([r for r in results if r["status"] == "error"]),
        "results": results,
    }


def _run_async(coro):
    """Run async coroutine synchronously inside Celery worker loop."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


@celery_app.task(name="app.tasks.analytics_tasks.refresh_all_campaign_analytics")
def refresh_all_campaign_analytics_task():
    """Celery task wrapper for refresh_all_campaign_analytics."""
    logger.info("Celery Task: Refreshing all campaign analytics...")
    result = _run_async(refresh_all_campaign_analytics())
    logger.info("Celery Task: Campaign analytics refresh completed: %s", result)
    return result