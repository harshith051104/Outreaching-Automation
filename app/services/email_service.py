"""
Email service - creation, tracking injection, and sending.

Backward-compatible wrappers that delegate to email_delivery/ subsystem.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Any

from fastapi import HTTPException, status

from app.config.mongodb_config import get_database
from app.utils.id_generator import generate_id, generate_tracking_id
from app.utils.email_utils import inject_tracking_pixel, replace_links_with_tracking

# Re-export email_delivery modules for callers that want the new API
from email_delivery.models import EmailStatus, RetryPolicy, EmailRecord, TrackingEvent  # noqa: F401
from email_delivery.delivery_manager import DeliveryManager  # noqa: F401
from email_delivery.persistence import EmailPersistence  # noqa: F401
from email_delivery.providers.base import BaseEmailProvider, ProviderResult  # noqa: F401
from email_delivery.providers.gmail import GmailProvider  # noqa: F401
from email_delivery.retry import RetryManager  # noqa: F401
from email_delivery.tracking.open_tracker import record_open as _record_open  # noqa: F401
from email_delivery.tracking.click_tracker import (  # noqa: F401
    record_click as _record_click,
    replace_links_with_tracking as _replace_links,
    build_click_tracking_url,
    parse_click_url,
)
from email_delivery.tracking.reply_detector import (  # noqa: F401
    record_reply as _record_reply,
    is_reply_from_lead,
    extract_reply_body,
)
from email_delivery.analytics import EngagementScorer, CampaignAnalytics  # noqa: F401
from email_delivery.sync_engine import poll_gmail_replies  # noqa: F401

logger = logging.getLogger(__name__)


async def create_email(user_id: str, data: Any, tracking_id: Optional[str] = None) -> dict:
    """Create an email record in the database. Backward-compatible wrapper."""
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
        "guardrail": getattr(data, "guardrail", None),
        "correlation_id": getattr(data, "correlation_id", None),
    }

    await db.emails.insert_one(email_doc)
    email_doc.pop("_id", None)
    return email_doc


async def send_campaign_email(email_id: str) -> dict:
    """Inject tracking, send via Gmail, and update email record.

    Delegates to email_delivery DeliveryManager for status transitions and retry,
    while preserving the existing campaign gate-keeper logic and HTTPException behavior.
    """
    db = await get_database()

    email = await db.emails.find_one({"id": email_id})
    if not email:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email not found.")

    if email["status"] == "sent":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email has already been sent.")

    # ── Campaign gate-keeper (pause / stop / daily limit) ──────────────────
    campaign_id = email.get("campaign_id")
    if campaign_id:
        campaign = await db.campaigns.find_one({"id": campaign_id})
        if campaign:
            if campaign.get("status") != "active":
                await db.emails.update_one(
                    {"id": email_id},
                    {"$set": {"status": "paused", "updated_at": datetime.now(timezone.utc)}},
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Campaign '{campaign.get('name', campaign_id)}' is not active "
                           f"(status: {campaign.get('status')}). Email send blocked.",
                )

            daily_limit = campaign.get("daily_send_limit")
            user_id = campaign.get("user_id")
            if user_id:
                prefs = await db.system_settings.find_one({"user_id": user_id, "type": "system_preferences"})
                if prefs and "dailyLimit" in prefs:
                    daily_limit = prefs["dailyLimit"]
            if daily_limit is None:
                daily_limit = 50

            hour_start = datetime.now(timezone.utc) - timedelta(hours=1)
            query = {
                "status": {"$in": ["sent", "pending", "sending", "paused"]},
                "created_at": {"$gte": hour_start}
            }
            gmail_account_id = email.get("gmail_account_id")
            if gmail_account_id:
                query["gmail_account_id"] = gmail_account_id
            elif user_id:
                query["user_id"] = user_id
            else:
                query["campaign_id"] = campaign_id

            sent_today = await db.emails.count_documents(query)
            if sent_today >= daily_limit:
                logger.info(
                    "Hourly send limit (%d) reached for campaign %s. Blocking email %s.",
                    daily_limit, campaign_id, email_id,
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Hourly send limit of {daily_limit} emails reached for campaign "
                           f"'{campaign.get('name', campaign_id)}'.",
                )
    # ────────────────────────────────────────────────────────────────────────

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
