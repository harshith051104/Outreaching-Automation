"""
Click tracking — records link click events and generates redirect URLs.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import quote, unquote

from app.config.mongodb_config import get_database
from app.config.settings import settings
from app.utils.id_generator import generate_id

from email_delivery.models import EmailRecord, EmailStatus, TrackingEvent
from email_delivery.config import email_config


def build_click_tracking_url(tracking_id: str, original_url: str) -> str:
    encoded_url = quote(original_url, safe="")
    return f"{settings.BACKEND_URL}/api/track/click/{tracking_id}?url={encoded_url}"


def replace_links_with_tracking(html: str, tracking_id: str) -> str:
    def replace_href(match: re.Match) -> str:
        full_tag = match.group(0)
        original_url = match.group(1).strip()
        if not original_url:
            return full_tag
        if original_url.startswith(("mailto:", "tel:", "#", "javascript:")):
            return full_tag
        tracked_url = build_click_tracking_url(tracking_id, original_url)
        return full_tag.replace(original_url, tracked_url)

    pattern = re.compile(r'<a[^>]*\shref=["\']([^"\']+)["\']', re.IGNORECASE)
    return pattern.sub(replace_href, html)


def parse_click_url(url_param: str) -> str:
    if not url_param or url_param == "None":
        return ""
    return unquote(url_param)


async def record_click(
    email: EmailRecord,
    url: str,
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
        event_type="click",
        ip_address=ip,
        user_agent=user_agent,
        metadata={"url": url},
        timestamp=now,
    )
    await db.tracking_events.insert_one(event.to_doc())

    if email.lead_id:
        await db.leads.update_one(
            {"id": email.lead_id},
            {"$inc": {"engagement_score": email_config.click_tracking_weight}},
        )

    current = EmailStatus(email.status)
    if current.can_transition_to(EmailStatus.CLICKED):
        await db.emails.update_one(
            {"id": email.id},
            {"$set": {"status": EmailStatus.CLICKED.value, "updated_at": now}},
        )

    await _update_campaign_analytics(email.campaign_id)
    await _dispatch_webhook(email, "link_clicked", url)

    return event


async def _update_campaign_analytics(campaign_id: str) -> None:
    try:
        from app.services.analytics_service import update_campaign_analytics
        await update_campaign_analytics(campaign_id)
    except Exception:
        pass


async def _dispatch_webhook(email: EmailRecord, event_type: str, url: str = "") -> None:
    try:
        from app.services.webhook_service import dispatch_event
        from app.schemas.campaign_v2 import WebhookEventType
        db = await get_database()
        campaign = await db.campaigns.find_one({"id": email.campaign_id}) if email.campaign_id else None
        await dispatch_event(
            event_type=WebhookEventType.LINK_CLICKED,
            campaign_id=email.campaign_id or "",
            campaign_name=campaign.get("name", "") if campaign else "",
            workspace=campaign.get("user_id", "") if campaign else "",
            data={
                "lead_email": email.to,
                "email_id": email.id,
                "link_url": url,
            },
        )
    except Exception:
        pass
