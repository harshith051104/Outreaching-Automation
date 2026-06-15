"""
Attachment tracking utilities.

Tracks when recipients view or download tracked attachments
(e.g., PDFs, documents) by serving them through the platform.
"""

from typing import Any


def generate_attachment_url(base_url: str, attachment_id: str, tracking_id: str) -> str:
    """
    Generate a tracked attachment URL.
    """
    return f"{base_url}/api/track/attachment/{attachment_id}?t={tracking_id}"


async def record_attachment_view(
    attachment_id: str, tracking_id: str, ip: str = "", user_agent: str = ""
) -> None:
    """
    Record an attachment view event in MongoDB and update lead engagement score.
    """
    from app.config.mongodb_config import get_database
    from app.utils.id_generator import generate_id
    from datetime import datetime, timezone

    db = await get_database()
    email = await db.emails.find_one({"tracking_id": tracking_id})
    if not email:
        return

    now = datetime.now(timezone.utc)

    event_doc = {
        "id": generate_id(),
        "tracking_id": tracking_id,
        "email_id": email["id"],
        "campaign_id": email.get("campaign_id"),
        "lead_id": email.get("lead_id"),
        "event_type": "attachment_view",
        "ip_address": ip,
        "user_agent": user_agent,
        "metadata": {"attachment_id": attachment_id},
        "timestamp": now,
    }
    await db.tracking_events.insert_one(event_doc)

    if email.get("lead_id"):
        await db.leads.update_one(
            {"id": email["lead_id"]},
            {"$inc": {"engagement_score": 3.0}},
        )