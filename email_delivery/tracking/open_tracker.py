"""
Open tracking — records email open events via tracking pixel.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.config.mongodb_config import get_database
from app.utils.id_generator import generate_id

from email_delivery.models import EmailRecord, EmailStatus, TrackingEvent
from email_delivery.config import email_config


async def record_open(
    email: EmailRecord,
    ip: str = "",
    user_agent: str = "",
) -> TrackingEvent | None:
    if not email.tracking_id:
        return None

    db = await get_database()
    now = datetime.now(timezone.utc)

    event = TrackingEvent(
        id=generate_id(),
        tracking_id=email.tracking_id,
        email_id=email.id,
        campaign_id=email.campaign_id,
        lead_id=email.lead_id,
        event_type="open",
        ip_address=ip,
        user_agent=user_agent,
        timestamp=now,
    )
    await db.tracking_events.insert_one(event.to_doc())

    if email.lead_id:
        await db.leads.update_one(
            {"id": email.lead_id},
            {"$inc": {"engagement_score": email_config.open_tracking_weight}},
        )

    current = EmailStatus(email.status)
    if current.can_transition_to(EmailStatus.OPENED):
        await db.emails.update_one(
            {"id": email.id},
            {"$set": {"status": EmailStatus.OPENED.value, "updated_at": now}},
        )

    await _update_campaign_analytics(email.campaign_id)
    await _update_tracker_checkboxes(email, {"email_opened": True})
    await _dispatch_webhook(email, "email_opened")

    return event


async def _update_campaign_analytics(campaign_id: str) -> None:
    try:
        from app.services.analytics_service import update_campaign_analytics
        await update_campaign_analytics(campaign_id)
    except Exception:
        pass


async def _update_tracker_checkboxes(email: EmailRecord, updates: dict) -> None:
    if not email.lead_id or not email.user_id:
        return
    try:
        from app.services.outreach_tracker_service import update_checkboxes
        await update_checkboxes(
            lead_id=email.lead_id,
            user_id=email.user_id,
            updates=updates,
            trigger_sync=False,
        )
    except Exception:
        pass


async def _dispatch_webhook(email: EmailRecord, event_type: str) -> None:
    try:
        from app.services.webhook_service import dispatch_event
        from app.schemas.campaign_v2 import WebhookEventType
        db = await get_database()
        campaign = await db.campaigns.find_one({"id": email.campaign_id}) if email.campaign_id else None
        await dispatch_event(
            event_type=WebhookEventType.EMAIL_OPENED,
            campaign_id=email.campaign_id or "",
            campaign_name=campaign.get("name", "") if campaign else "",
            workspace=campaign.get("user_id", "") if campaign else "",
            data={
                "lead_email": email.to,
                "email_id": email.id,
                "email_subject": email.subject,
            },
        )
    except Exception:
        pass
