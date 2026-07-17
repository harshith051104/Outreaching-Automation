"""
Workflow trigger — publishes events to downstream systems.

Dispatches webhook events and WebSocket notifications.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from reply.models import WorkflowEvent, WorkflowEventType

logger = logging.getLogger(__name__)


async def publish_events(events: List[WorkflowEvent]) -> None:
    """Publish a list of workflow events."""
    for event in events:
        await publish_event(event)


async def publish_event(event: WorkflowEvent) -> None:
    """Publish a single workflow event."""
    # 1. Webhook dispatch
    await _dispatch_webhook(event)
    # 2. WebSocket broadcast
    await _broadcast_websocket(event)


async def _dispatch_webhook(event: WorkflowEvent) -> None:
    """Dispatch event to configured webhooks."""
    try:
        from app.services.webhook_service import dispatch_event
        from app.schemas.campaign_v2 import WebhookEventType

        # Map our event type to WebhookEventType
        webhook_type_map = {
            WorkflowEventType.REPLY_RECEIVED: WebhookEventType.REPLY_RECEIVED,
            WorkflowEventType.MEETING_REQUESTED: WebhookEventType.LEAD_MEETING_BOOKED,
            WorkflowEventType.CAMPAIGN_PAUSED: WebhookEventType.LEAD_NEUTRAL,
            WorkflowEventType.CAMPAIGN_STOPPED: WebhookEventType.LEAD_NOT_INTERESTED,
            WorkflowEventType.LEAD_UPDATED: WebhookEventType.LEAD_INTERESTED,
            WorkflowEventType.UNSUBSCRIBE_RECEIVED: WebhookEventType.LEAD_UNSUBSCRIBED,
        }

        webhook_type = webhook_type_map.get(event.event_type)
        if not webhook_type:
            return

        # Get campaign name for the webhook
        db = await __import__("app.config.mongodb_config", fromlist=["get_database"]).get_database()
        campaign = await db.campaigns.find_one({"id": event.campaign_id}) if event.campaign_id else None

        await dispatch_event(
            event_type=webhook_type,
            campaign_id=event.campaign_id,
            campaign_name=campaign.get("name", "") if campaign else "",
            workspace=event.user_id,
            data=event.data,
        )
    except Exception as exc:
        logger.warning("Webhook dispatch failed for %s: %s", event.event_type.value, exc)


async def _broadcast_websocket(event: WorkflowEvent) -> None:
    """Broadcast event via WebSocket."""
    try:
        from app.websocket.connection_manager import manager
        if event.user_id:
            await manager.broadcast_reply(event.user_id, {
                "event_type": event.event_type.value,
                "campaign_id": event.campaign_id,
                "lead_id": event.lead_id,
                "data": event.data,
            })
    except Exception:
        pass
