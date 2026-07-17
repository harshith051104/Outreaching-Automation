"""
Activity Feed — chronological activity stream with real-time push.

Maintains an append-only log of user and system actions.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from dashboard.models import ActivityItem, WSEvent, EventType
from dashboard.websocket_manager import dashboard_ws_manager
from dashboard.config import dashboard_config

logger = logging.getLogger(__name__)


async def record_activity(
    user_id: str,
    user_name: str,
    action: str,
    reference_id: str = "",
    reference_type: str = "",
    details: str = "",
    metadata: Optional[Dict[str, Any]] = None,
    push_ws: bool = True,
) -> ActivityItem:
    """Record an activity item and optionally push via WebSocket."""
    item = ActivityItem(
        user_id=user_id,
        user_name=user_name,
        action=action,
        reference_id=reference_id,
        reference_type=reference_type,
        details=details,
        metadata=metadata or {},
    )

    # Persist to MongoDB
    try:
        from app.config.mongodb_config import get_database
        db = await get_database()
        doc = item.to_dict()
        doc["_id"] = doc.pop("id")
        await db.activity_logs.insert_one(doc)
    except Exception as exc:
        logger.warning("Failed to persist activity: %s", exc)

    # Push via WebSocket
    if push_ws and dashboard_config.activity.push_enabled:
        event = WSEvent(
            event_type=EventType.DASHBOARD_REFRESH.value,
            data={"activity": item.to_dict()},
            user_id=user_id,
        )
        await dashboard_ws_manager.send_to_user(user_id, event)

    return item


async def get_activity_feed(
    user_id: str = "",
    action_filter: str = "",
    limit: int = 50,
    offset: int = 0,
) -> List[ActivityItem]:
    """Get activity feed with optional filters."""
    try:
        from app.config.mongodb_config import get_database
        db = await get_database()
        query: Dict[str, Any] = {}
        if user_id:
            query["user_id"] = user_id
        if action_filter:
            query["action"] = action_filter

        cursor = db.activity_logs.find(query).sort("created_at", -1).skip(offset).limit(limit)
        docs = await cursor.to_list(length=limit)
        return [
            ActivityItem(
                id=d.get("_id", d.get("id", "")),
                user_id=d.get("user_id", ""),
                user_name=d.get("user_name", ""),
                action=d.get("action", ""),
                reference_id=d.get("reference_id", ""),
                reference_type=d.get("reference_type", ""),
                details=d.get("details", ""),
                metadata=d.get("metadata", {}),
                created_at=str(d.get("created_at", "")),
            )
            for d in docs
        ]
    except Exception as exc:
        logger.error("Failed to get activity feed: %s", exc)
        return []


async def get_activity_count(user_id: str = "") -> int:
    """Get total activity count."""
    try:
        from app.config.mongodb_config import get_database
        db = await get_database()
        query = {"user_id": user_id} if user_id else {}
        return await db.activity_logs.count_documents(query)
    except Exception:
        return 0


async def broadcast_campaign_activity(
    campaign_id: str,
    action: str,
    details: str = "",
    user_id: str = "",
    user_name: str = "",
) -> None:
    """Broadcast a campaign activity to all subscribed users."""
    event = WSEvent(
        event_type=f"campaign.{action}" if not action.startswith("campaign.") else action,
        data={
            "campaign_id": campaign_id,
            "action": action,
            "details": details,
            "user_name": user_name,
        },
        campaign_id=campaign_id,
        user_id=user_id,
    )
    await dashboard_ws_manager.broadcast_to_campaign(campaign_id, event)
