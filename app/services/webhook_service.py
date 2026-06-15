"""
Webhook service layer.

Manages webhook subscriptions and sends event notifications
for email events, lead status changes, and campaign updates.
"""

import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from app.config.mongodb_config import get_database
from app.schemas.campaign_v2 import WebhookEventType, WebhookEventPayload
from app.utils.id_generator import generate_id

logger = logging.getLogger(__name__)


async def create_webhook(user_id: str, url: str, events: list[str], secret: Optional[str] = None) -> dict:
    """Create a new webhook subscription."""
    db = await get_database()

    webhook_doc = {
        "id": generate_id(),
        "user_id": user_id,
        "url": url,
        "events": events,
        "is_active": True,
        "secret": secret,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    await db.webhooks.insert_one(webhook_doc)
    webhook_doc.pop("_id", None)
    return webhook_doc


async def get_webhooks(user_id: str) -> list:
    """List all webhooks for a user."""
    db = await get_database()
    cursor = db.webhooks.find({"user_id": user_id}, {"_id": 0}).sort("created_at", -1)
    return await cursor.to_list(length=100)


async def get_webhook(webhook_id: str, user_id: str) -> Optional[dict]:
    """Get a single webhook."""
    db = await get_database()
    return await db.webhooks.find_one({"id": webhook_id, "user_id": user_id}, {"_id": 0})


async def update_webhook(webhook_id: str, user_id: str, data: dict) -> Optional[dict]:
    """Update a webhook."""
    db = await get_database()
    data["updated_at"] = datetime.now(timezone.utc)
    result = await db.webhooks.update_one(
        {"id": webhook_id, "user_id": user_id},
        {"$set": data},
    )
    if result.matched_count == 0:
        return None
    return await get_webhook(webhook_id, user_id)


async def delete_webhook(webhook_id: str, user_id: str) -> bool:
    """Delete a webhook."""
    db = await get_database()
    result = await db.webhooks.delete_one({"id": webhook_id, "user_id": user_id})
    return result.deleted_count > 0


async def dispatch_event(
    event_type: WebhookEventType,
    campaign_id: str,
    campaign_name: str,
    workspace: str,
    data: dict[str, Any],
):
    """
    Dispatch a webhook event to all matching active webhooks.
    """
    db = await get_database()

    cursor = db.webhooks.find(
        {"is_active": True, "events": {"$in": [event_type.value, "all"]}},
        {"_id": 0},
    )
    webhooks = await cursor.to_list(length=100)

    if not webhooks:
        return

    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type.value,
        "workspace": workspace,
        "campaign_id": campaign_id,
        "campaign_name": campaign_name,
        **data,
    }

    for webhook in webhooks:
        try:
            await _send_webhook(webhook, payload)
        except Exception as exc:
            logger.exception("Webhook delivery failed for %s: %s", webhook["url"], exc)
            await _record_webhook_event(webhook["id"], payload, "failed", str(exc))


async def _send_webhook(webhook: dict, payload: dict):
    """Send a webhook payload and record the result."""
    url = webhook["url"]
    secret = webhook.get("secret")

    headers = {"Content-Type": "application/json"}
    body = json.dumps(payload, default=str)

    if secret:
        signature = hmac.new(
            secret.encode(), body.encode(), hashlib.sha256
        ).hexdigest()
        headers["X-Webhook-Signature"] = f"sha256={signature}"

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(url, content=body, headers=headers)

    status_code = "success" if response.status_code < 400 else "failed"
    await _record_webhook_event(
        webhook["id"], payload, status_code,
        error=response.text if status_code == "failed" else None,
    )


async def _record_webhook_event(
    webhook_id: str, payload: dict, status: str, error: Optional[str] = None
):
    """Record a webhook delivery attempt."""
    db = await get_database()

    event_doc = {
        "id": generate_id(),
        "webhook_id": webhook_id,
        "event_type": payload.get("event_type"),
        "status": status,
        "payload": payload,
        "error": error,
        "created_at": datetime.now(timezone.utc),
    }

    await db.webhook_events.insert_one(event_doc)


async def get_webhook_events(
    webhook_id: Optional[str] = None,
    user_id: Optional[str] = None,
    limit: int = 50,
) -> list:
    """Get webhook delivery events."""
    db = await get_database()
    query: dict[str, Any] = {}
    if webhook_id:
        query["webhook_id"] = webhook_id
    if user_id:
        query["user_id"] = user_id

    cursor = db.webhook_events.find(query, {"_id": 0}).sort("created_at", -1).limit(limit)
    return await cursor.to_list(length=limit)


async def get_webhook_event_stats(webhook_id: str) -> dict:
    """Get aggregate stats for webhook events."""
    db = await get_database()

    pipeline = [
        {"$match": {"webhook_id": webhook_id}},
        {"$group": {"_id": "$status", "count": {"$sum": 1}}},
    ]
    results = await db.webhook_events.aggregate(pipeline).to_list(length=10)

    stats = {"success": 0, "failed": 0, "pending": 0}
    for r in results:
        stats[r["_id"]] = r["count"]

    total = sum(stats.values())
    return {
        "webhook_id": webhook_id,
        "total_events": total,
        "success_count": stats["success"],
        "failed_count": stats["failed"],
        "pending_count": stats["pending"],
        "success_rate": round(stats["success"] / total * 100, 2) if total > 0 else 0,
    }


def get_available_event_types() -> list[dict]:
    """Return all available webhook event types with descriptions."""
    return [
        {"event_type": "email_sent", "category": "email", "description": "An email was sent"},
        {"event_type": "email_opened", "category": "email", "description": "A lead opened an email"},
        {"event_type": "reply_received", "category": "email", "description": "A reply was received from a lead"},
        {"event_type": "auto_reply_received", "category": "email", "description": "An auto-reply was received"},
        {"event_type": "link_clicked", "category": "email", "description": "A lead clicked a tracked link"},
        {"event_type": "email_bounced", "category": "email", "description": "An email bounced"},
        {"event_type": "lead_unsubscribed", "category": "email", "description": "A lead unsubscribed"},
        {"event_type": "account_error", "category": "email", "description": "An account-level error occurred"},
        {"event_type": "campaign_completed", "category": "campaign", "description": "A campaign completed"},
        {"event_type": "lead_neutral", "category": "lead", "description": "Lead marked as neutral"},
        {"event_type": "lead_interested", "category": "lead", "description": "Lead marked as interested"},
        {"event_type": "lead_not_interested", "category": "lead", "description": "Lead marked as not interested"},
        {"event_type": "lead_meeting_booked", "category": "lead", "description": "A meeting was booked"},
        {"event_type": "lead_meeting_completed", "category": "lead", "description": "A meeting was completed"},
        {"event_type": "lead_closed", "category": "lead", "description": "Lead marked as closed"},
        {"event_type": "lead_out_of_office", "category": "lead", "description": "Lead is out of office"},
        {"event_type": "lead_wrong_person", "category": "lead", "description": "Lead marked as wrong person"},
    ]