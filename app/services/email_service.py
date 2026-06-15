"""
Email service - creation, tracking injection, and sending.
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Any

from fastapi import HTTPException, status

from app.config.mongodb_config import get_database
from app.utils.id_generator import generate_id, generate_tracking_id
from app.utils.email_utils import inject_tracking_pixel, replace_links_with_tracking

logger = logging.getLogger(__name__)


async def create_email(user_id: str, data: Any, tracking_id: Optional[str] = None) -> dict:
    """Create an email record in the database."""
    db = await get_database()
    now = datetime.now(timezone.utc)

    email_doc = {
        "id": generate_id(),
        "user_id": user_id,
        "campaign_id": data.campaign_id,
        "lead_id": data.lead_id,
        "gmail_account_id": data.gmail_account_id,
        "to": data.to,
        "subject": data.subject,
        "body_html": data.body_html,
        "tracking_id": tracking_id or generate_tracking_id(),
        "sequence_number": getattr(data, "sequence_number", 1),
        "attachments": getattr(data, "attachments", None) or [],
        "status": "draft",
        "gmail_message_id": None,
        "gmail_thread_id": None,
        "sent_at": None,
        "created_at": now,
        "updated_at": now,
    }

    await db.emails.insert_one(email_doc)
    email_doc.pop("_id", None)
    return email_doc


async def send_campaign_email(email_id: str) -> dict:
    """Inject tracking, send via Gmail, and update email record."""
    db = await get_database()

    email = await db.emails.find_one({"id": email_id})
    if not email:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email not found.")

    if email["status"] == "sent":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email has already been sent.")

    tracking_id = email["tracking_id"]
    body_html = inject_tracking_pixel(email["body_html"], tracking_id)
    body_html = replace_links_with_tracking(body_html, tracking_id)

    from app.services.gmail_service import send_email as gmail_send

    attachments = email.get("attachments", [])

    try:
        result = await gmail_send(
            gmail_account_id=email["gmail_account_id"],
            to=email["to"],
            subject=email["subject"],
            body_html=body_html,
            thread_id=email.get("gmail_thread_id"),
            attachments=attachments if attachments else None,
        )
    except Exception as exc:
        await db.emails.update_one(
            {"id": email_id},
            {"$set": {"status": "failed", "error_message": str(exc), "updated_at": datetime.now(timezone.utc)}},
        )
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Failed to send email: {exc}")

    now = datetime.now(timezone.utc)
    await db.emails.update_one(
        {"id": email_id},
        {
            "$set": {
                "status": "sent",
                "gmail_message_id": result.get("gmail_message_id"),
                "gmail_thread_id": result.get("gmail_thread_id"),
                "sent_at": now,
                "updated_at": now,
            }
        },
    )

    await db.campaigns.update_one(
        {"id": email["campaign_id"]},
        {"$inc": {"emails_sent": 1}},
    )

    try:
        from app.services.analytics_service import update_campaign_analytics
        await update_campaign_analytics(email["campaign_id"])
    except Exception as exc:
        logger.warning("Failed to update campaign analytics for campaign %s: %s", email.get("campaign_id"), exc)

    email.pop("_id", None)
    email["status"] = "sent"
    email["gmail_message_id"] = result.get("gmail_message_id")
    email["gmail_thread_id"] = result.get("gmail_thread_id")
    email["sent_at"] = now
    return email


async def get_campaign_emails(campaign_id: str, skip: int = 0, limit: int = 50) -> list:
    """List emails for a campaign."""
    db = await get_database()
    cursor = (
        db.emails.find({"campaign_id": campaign_id}, {"_id": 0})
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
    )
    return await cursor.to_list(length=limit)


async def get_email(email_id: str) -> dict:
    """Get a single email."""
    db = await get_database()
    email = await db.emails.find_one({"id": email_id}, {"_id": 0})
    if not email:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email not found.")
    return email