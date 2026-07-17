"""
Tracking service layer.

Backward-compatible wrappers that delegate to email_delivery/ tracking modules.
"""

from datetime import datetime, timezone

from app.config.mongodb_config import get_database
from app.utils.id_generator import generate_id

# Re-export email_delivery tracking modules for callers that want the new API
from email_delivery.tracking.open_tracker import record_open as _record_open_new  # noqa: F401
from email_delivery.tracking.click_tracker import (  # noqa: F401
    record_click as _record_click_new,
    build_click_tracking_url,
    replace_links_with_tracking,
    parse_click_url,
)
from email_delivery.tracking.reply_detector import (  # noqa: F401
    record_reply as _record_reply_new,
    is_reply_from_lead,
    extract_reply_body,
)
from email_delivery.models import EmailRecord, EmailStatus  # noqa: F401
from email_delivery.persistence import EmailPersistence  # noqa: F401
from email_delivery.analytics import EngagementScorer, CampaignAnalytics  # noqa: F401


async def _get_email_by_tracking_id(tracking_id: str) -> dict | None:
    """Resolve a tracking_id to its email document."""
    db = await get_database()
    return await db.emails.find_one({"tracking_id": tracking_id})


async def record_open(tracking_id: str, ip: str, user_agent: str) -> None:
    """
    Record an email open event.

    Backward-compatible wrapper. Delegates to email_delivery.tracking.open_tracker
    for the core logic while preserving the existing call signature.
    """
    email_doc = await _get_email_by_tracking_id(tracking_id)
    if not email_doc:
        return

    email_record = EmailRecord.from_doc({k: v for k, v in email_doc.items() if k != "_id"})
    await _record_open_new(email_record, ip=ip, user_agent=user_agent)


async def record_click(
    tracking_id: str, url: str, ip: str, user_agent: str
) -> None:
    """Record a link click event. Backward-compatible wrapper."""
    email_doc = await _get_email_by_tracking_id(tracking_id)
    if not email_doc:
        return

    email_record = EmailRecord.from_doc({k: v for k, v in email_doc.items() if k != "_id"})
    await _record_click_new(email_record, url=url, ip=ip, user_agent=user_agent)


async def record_reply(tracking_id: str, reply_data: dict, gmail_thread_id: str = "") -> None:
    """
    Record a reply event and store the reply document.

    Backward-compatible wrapper. Delegates to email_delivery.tracking.reply_detector.
    """
    await _record_reply_new(tracking_id, reply_data, gmail_thread_id=gmail_thread_id)


async def get_tracking_events(campaign_id: str) -> list:
    """Get all tracking events for a campaign, newest first."""
    db = await get_database()
    cursor = (
        db.tracking_events.find({"campaign_id": campaign_id}, {"_id": 0})
        .sort("timestamp", -1)
        .limit(500)
    )
    return await cursor.to_list(length=500)


async def get_email_tracking(tracking_id: str) -> list:
    """Get all tracking events for a specific email by tracking_id."""
    db = await get_database()
    cursor = (
        db.tracking_events.find({"tracking_id": tracking_id}, {"_id": 0})
        .sort("timestamp", -1)
    )
    return await cursor.to_list(length=200)


async def get_tracking_stats(campaign_id: str) -> dict:
    """Aggregate open/click/reply counts for a campaign."""
    db = await get_database()

    pipeline = [
        {"$match": {"campaign_id": campaign_id}},
        {
            "$group": {
                "_id": "$event_type",
                "count": {"$sum": 1},
                "unique_emails": {"$addToSet": "$email_id"},
            }
        },
    ]
    results = await db.tracking_events.aggregate(pipeline).to_list(length=10)

    stats: dict = {
        "campaign_id": campaign_id,
        "opens": 0,
        "unique_opens": 0,
        "clicks": 0,
        "unique_clicks": 0,
        "replies": 0,
    }

    for r in results:
        event_type = r["_id"]
        if event_type == "open":
            stats["opens"] = r["count"]
            stats["unique_opens"] = len(r["unique_emails"])
        elif event_type == "click":
            stats["clicks"] = r["count"]
            stats["unique_clicks"] = len(r["unique_emails"])
        elif event_type == "reply":
            stats["replies"] = r["count"]

    return stats
