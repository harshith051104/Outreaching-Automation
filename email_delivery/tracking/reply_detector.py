"""
Reply detection — detects and records reply events from Gmail threads.
"""

from __future__ import annotations

import base64
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.config.mongodb_config import get_database
from app.utils.id_generator import generate_id

from email_delivery.models import EmailRecord, EmailStatus, TrackingEvent


def is_reply_from_lead(from_header: str, lead_email: str) -> bool:
    if not from_header or not lead_email:
        return False
    if "<" in from_header:
        email = from_header.split("<")[1].split(">")[0].strip()
    else:
        email = from_header.strip()
    return email.lower() == lead_email.lower()


def extract_reply_body(message_payload: dict) -> str:
    body = ""
    if message_payload.get("body", {}).get("data"):
        try:
            body = base64.urlsafe_b64decode(
                message_payload["body"]["data"]
            ).decode("utf-8", errors="replace")
        except Exception:
            pass

    if not body and message_payload.get("parts"):
        for part in message_payload["parts"]:
            if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
                try:
                    body = base64.urlsafe_b64decode(
                        part["body"]["data"]
                    ).decode("utf-8", errors="replace")
                    break
                except Exception:
                    continue
            elif part.get("mimeType") == "text/html" and part.get("body", {}).get("data") and not body:
                try:
                    body = base64.urlsafe_b64decode(
                        part["body"]["data"]
                    ).decode("utf-8", errors="replace")
                except Exception:
                    continue
    return body


async def record_reply(
    tracking_id: str,
    reply_data: Dict[str, Any],
    gmail_thread_id: str = "",
) -> Optional[TrackingEvent]:
    db = await get_database()
    email_doc = await db.emails.find_one({"tracking_id": tracking_id})
    if not email_doc:
        return None

    gmail_message_id = reply_data.get("gmail_message_id")
    if gmail_message_id:
        existing = await db.replies.find_one({"gmail_message_id": gmail_message_id})
        if existing:
            return None

    now = datetime.now(timezone.utc)

    event = TrackingEvent(
        id=generate_id(),
        tracking_id=tracking_id,
        email_id=email_doc["id"],
        campaign_id=email_doc.get("campaign_id", ""),
        lead_id=email_doc.get("lead_id", ""),
        event_type="reply",
        metadata=reply_data,
        timestamp=now,
    )
    await db.tracking_events.insert_one(event.to_doc())

    if not gmail_thread_id:
        gmail_thread_id = email_doc.get("gmail_thread_id", "")

    reply_doc = {
        "id": generate_id(),
        "email_id": email_doc["id"],
        "campaign_id": email_doc.get("campaign_id"),
        "lead_id": email_doc.get("lead_id"),
        "gmail_message_id": gmail_message_id or "",
        "gmail_thread_id": gmail_thread_id,
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

    if email_doc.get("lead_id"):
        await db.leads.update_one(
            {"id": email_doc["lead_id"]},
            {
                "$inc": {"engagement_score": 5.0},
                "$set": {"status": "replied", "updated_at": now},
            },
        )

    if email_doc.get("lead_id"):
        try:
            from app.services.followup_service import cancel_lead_followups
            await cancel_lead_followups(email_doc["lead_id"])
        except Exception:
            pass

    if email_doc.get("campaign_id"):
        try:
            from app.services.analytics_service import update_campaign_analytics
            await update_campaign_analytics(email_doc["campaign_id"])
        except Exception:
            pass

    if email_doc.get("lead_id") and email_doc.get("user_id"):
        try:
            from app.services.outreach_tracker_service import update_checkboxes
            await update_checkboxes(
                lead_id=email_doc["lead_id"],
                user_id=email_doc["user_id"],
                updates={"email_replied": True, "email_opened": True},
                trigger_sync=True,
            )
        except Exception:
            pass

    try:
        from app.services.webhook_service import dispatch_event
        from app.schemas.campaign_v2 import WebhookEventType
        campaign = None
        if email_doc.get("campaign_id"):
            campaign = await db.campaigns.find_one({"id": email_doc["campaign_id"]})
        await dispatch_event(
            event_type=WebhookEventType.REPLY_RECEIVED,
            campaign_id=email_doc.get("campaign_id", ""),
            campaign_name=campaign.get("name", "") if campaign else "",
            workspace=campaign.get("user_id", "") if campaign else "",
            data={
                "lead_email": reply_data.get("from", ""),
                "email_id": email_doc.get("id", ""),
                "email_subject": reply_data.get("subject", ""),
                "reply_text_snippet": reply_data.get("snippet", ""),
            },
        )
    except Exception:
        pass

    return event
