"""
Notification Service — CRUD and real-time push.

Extends the existing notification_service.py with WebSocket push.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from dashboard.models import DashboardNotification, NotificationSeverity, WSEvent, EventType
from dashboard.websocket_manager import dashboard_ws_manager
from dashboard.config import dashboard_config

logger = logging.getLogger(__name__)


async def create_notification(
    user_id: str,
    type: str,
    title: str,
    message: str,
    severity: NotificationSeverity = NotificationSeverity.INFO,
    reference_id: str = "",
    reference_type: str = "",
    push_ws: bool = True,
) -> DashboardNotification:
    """Create a notification and optionally push via WebSocket."""
    notif = DashboardNotification(
        user_id=user_id,
        type=type,
        title=title,
        message=message,
        severity=severity,
        reference_id=reference_id,
        reference_type=reference_type,
    )

    # Persist to MongoDB
    try:
        from app.config.mongodb_config import get_database
        db = await get_database()
        doc = notif.to_dict()
        doc["_id"] = doc.pop("id")
        await db.notifications.insert_one(doc)
    except Exception as exc:
        logger.warning("Failed to persist notification: %s", exc)

    # Push via WebSocket
    if push_ws and dashboard_config.notification.push_enabled:
        event = WSEvent(
            event_type=EventType.NOTIFICATION_CREATED.value,
            data=notif.to_dict(),
            user_id=user_id,
        )
        await dashboard_ws_manager.send_to_user(user_id, event)

    return notif


async def get_notifications(
    user_id: str,
    unread_only: bool = False,
    limit: int = 50,
) -> List[DashboardNotification]:
    """Get notifications for a user."""
    try:
        from app.config.mongodb_config import get_database
        db = await get_database()
        query: Dict[str, Any] = {"user_id": user_id}
        if unread_only:
            query["is_read"] = False

        cursor = db.notifications.find(query).sort("created_at", -1).limit(limit)
        docs = await cursor.to_list(length=limit)
        return [
            DashboardNotification(
                id=d.get("_id", d.get("id", "")),
                user_id=d.get("user_id", ""),
                type=d.get("type", ""),
                title=d.get("title", ""),
                message=d.get("message", ""),
                severity=NotificationSeverity(d.get("severity", "info")),
                reference_id=d.get("reference_id", ""),
                reference_type=d.get("reference_type", ""),
                is_read=d.get("is_read", False),
                created_at=str(d.get("created_at", "")),
            )
            for d in docs
        ]
    except Exception as exc:
        logger.error("Failed to get notifications: %s", exc)
        return []


async def get_unread_count(user_id: str) -> int:
    """Get unread notification count."""
    try:
        from app.config.mongodb_config import get_database
        db = await get_database()
        return await db.notifications.count_documents({"user_id": user_id, "is_read": False})
    except Exception:
        return 0


async def mark_read(user_id: str, notification_id: str) -> bool:
    """Mark a single notification as read."""
    try:
        from app.config.mongodb_config import get_database
        db = await get_database()
        result = await db.notifications.update_one(
            {"_id": notification_id, "user_id": user_id},
            {"$set": {"is_read": True}},
        )
        return result.modified_count > 0
    except Exception:
        return False


async def mark_all_read(user_id: str) -> int:
    """Mark all notifications as read. Returns count updated."""
    try:
        from app.config.mongodb_config import get_database
        db = await get_database()
        result = await db.notifications.update_many(
            {"user_id": user_id, "is_read": False},
            {"$set": {"is_read": True}},
        )
        return result.modified_count
    except Exception:
        return 0


async def delete_notification(user_id: str, notification_id: str) -> bool:
    """Delete a notification."""
    try:
        from app.config.mongodb_config import get_database
        db = await get_database()
        result = await db.notifications.delete_one({"_id": notification_id, "user_id": user_id})
        return result.deleted_count > 0
    except Exception:
        return False


async def delete_all(user_id: str) -> int:
    """Delete all notifications for a user."""
    try:
        from app.config.mongodb_config import get_database
        db = await get_database()
        result = await db.notifications.delete_many({"user_id": user_id})
        return result.deleted_count
    except Exception:
        return 0
