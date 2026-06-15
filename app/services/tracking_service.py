"""
Tracking service layer.

Records email open, click, and reply events and provides
aggregated tracking statistics for campaigns.

Enhanced to dispatch webhook events for real-time notifications.
"""

from datetime import datetime, timezone

from app.config.mongodb_config import get_database
from app.utils.id_generator import generate_id


async def _get_email_by_tracking_id(tracking_id: str) -> dict | None:
    """Resolve a tracking_id to its email document."""
    db = await get_database()
    return await db.emails.find_one({"tracking_id": tracking_id})


async def record_open(tracking_id: str, ip: str, user_agent: str) -> None:
    """
    Record an email open event.

    Looks up the email by tracking_id, creates a tracking event,
    and bumps the lead's engagement score.
    """
    email = await _get_email_by_tracking_id(tracking_id)
    if not email:
        return

    db = await get_database()
    now = datetime.now(timezone.utc)

    event_doc = {
        "id": generate_id(),
        "tracking_id": tracking_id,
        "email_id": email["id"],
        "campaign_id": email.get("campaign_id"),
        "lead_id": email.get("lead_id"),
        "event_type": "open",
        "ip_address": ip,
        "user_agent": user_agent,
        "metadata": {},
        "timestamp": now,
    }
    await db.tracking_events.insert_one(event_doc)

    if email.get("lead_id"):
        await db.leads.update_one(
            {"id": email["lead_id"]},
            {"$inc": {"engagement_score": 1.0}},
        )

    if email.get("campaign_id"):
        from app.services.analytics_service import update_campaign_analytics
        await update_campaign_analytics(email["campaign_id"])

    try:
        from app.services.webhook_service import dispatch_event
        from app.schemas.campaign_v2 import WebhookEventType

        campaign = None
        if email.get("campaign_id"):
            campaign = await db.campaigns.find_one({"id": email["campaign_id"]})

        await dispatch_event(
            event_type=WebhookEventType.EMAIL_OPENED,
            campaign_id=email.get("campaign_id", ""),
            campaign_name=campaign.get("name", "") if campaign else "",
            workspace=campaign.get("user_id", "") if campaign else "",
            data={
                "lead_email": email.get("to_email", ""),
                "email_account": email.get("from_email", ""),
                "email_id": email.get("id", ""),
                "email_subject": email.get("subject", ""),
            },
        )
    except Exception:
        pass


async def record_click(
    tracking_id: str, url: str, ip: str, user_agent: str
) -> None:
    """Record a link click event."""
    email = await _get_email_by_tracking_id(tracking_id)
    if not email:
        return

    db = await get_database()
    now = datetime.now(timezone.utc)

    event_doc = {
        "id": generate_id(),
        "tracking_id": tracking_id,
        "email_id": email["id"],
        "campaign_id": email.get("campaign_id"),
        "lead_id": email.get("lead_id"),
        "event_type": "click",
        "ip_address": ip,
        "user_agent": user_agent,
        "metadata": {"url": url},
        "timestamp": now,
    }
    await db.tracking_events.insert_one(event_doc)

    if email.get("lead_id"):
        await db.leads.update_one(
            {"id": email["lead_id"]},
            {"$inc": {"engagement_score": 2.0}},
        )

    if email.get("campaign_id"):
        from app.services.analytics_service import update_campaign_analytics
        await update_campaign_analytics(email["campaign_id"])

    try:
        from app.services.webhook_service import dispatch_event
        from app.schemas.campaign_v2 import WebhookEventType

        campaign = None
        if email.get("campaign_id"):
            campaign = await db.campaigns.find_one({"id": email["campaign_id"]})

        await dispatch_event(
            event_type=WebhookEventType.LINK_CLICKED,
            campaign_id=email.get("campaign_id", ""),
            campaign_name=campaign.get("name", "") if campaign else "",
            workspace=campaign.get("user_id", "") if campaign else "",
            data={
                "lead_email": email.get("to_email", ""),
                "email_account": email.get("from_email", ""),
                "email_id": email.get("id", ""),
                "link_url": url,
            },
        )
    except Exception:
        pass


async def record_reply(tracking_id: str, reply_data: dict, gmail_thread_id: str = "") -> None:
    """
    Record a reply event and store the reply document.

    reply_data should contain: gmail_message_id, from, subject, snippet, date
    gmail_thread_id is optional - if provided, the reply can be sent in the same thread later.
    """
    email = await _get_email_by_tracking_id(tracking_id)
    if not email:
        return

    db = await get_database()

    gmail_message_id = reply_data.get("gmail_message_id")
    if gmail_message_id:
        existing_reply = await db.replies.find_one({"gmail_message_id": gmail_message_id})
        if existing_reply:
            return

    now = datetime.now(timezone.utc)

    event_doc = {
        "id": generate_id(),
        "tracking_id": tracking_id,
        "email_id": email["id"],
        "campaign_id": email.get("campaign_id"),
        "lead_id": email.get("lead_id"),
        "event_type": "reply",
        "ip_address": "",
        "user_agent": "",
        "metadata": reply_data,
        "timestamp": now,
    }
    await db.tracking_events.insert_one(event_doc)

    # If gmail_thread_id not passed directly, try to get it from the original email document
    if not gmail_thread_id:
        gmail_thread_id = email.get("gmail_thread_id", "")

    reply_doc = {
        "id": generate_id(),
        "email_id": email["id"],
        "campaign_id": email.get("campaign_id"),
        "lead_id": email.get("lead_id"),
        "gmail_message_id": reply_data.get("gmail_message_id", ""),
        "gmail_thread_id": gmail_thread_id,  # Store thread ID for reply threading
        "from_email": reply_data.get("from", ""),
        "subject": reply_data.get("subject", ""),
        "snippet": reply_data.get("snippet", ""),
        "body": reply_data.get("body", ""),
        "classification": None,
        "sentiment": None,
        "received_at": now,
        "created_at": now,
    }
    await db.replies.insert_one(reply_doc)

    if email.get("lead_id"):
        await db.leads.update_one(
            {"id": email["lead_id"]},
            {
                "$inc": {"engagement_score": 5.0},
                "$set": {"status": "replied", "updated_at": now},
            },
        )

    if email.get("lead_id"):
        from app.services.followup_service import cancel_lead_followups
        await cancel_lead_followups(email["lead_id"])

    if email.get("campaign_id"):
        from app.services.analytics_service import update_campaign_analytics
        await update_campaign_analytics(email["campaign_id"])

    try:
        from app.services.webhook_service import dispatch_event
        from app.schemas.campaign_v2 import WebhookEventType

        campaign = None
        if email.get("campaign_id"):
            campaign = await db.campaigns.find_one({"id": email["campaign_id"]})

        await dispatch_event(
            event_type=WebhookEventType.REPLY_RECEIVED,
            campaign_id=email.get("campaign_id", ""),
            campaign_name=campaign.get("name", "") if campaign else "",
            workspace=campaign.get("user_id", "") if campaign else "",
            data={
                "lead_email": reply_data.get("from", ""),
                "email_id": email.get("id", ""),
                "email_subject": reply_data.get("subject", ""),
                "reply_text_snippet": reply_data.get("snippet", ""),
                "reply_subject": reply_data.get("subject", ""),
            },
        )
    except Exception:
        pass


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
    """
    Aggregate open/click/reply counts for a campaign.
    """
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