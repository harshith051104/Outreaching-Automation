"""
LinkedIn Notification Service

Handles inserting notifications for connection acceptances, message replies, etc.
into MongoDB and publishes real-time push alerts to active WebSocket sessions.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.config.mongodb_config import get_database
from app.websocket.connection_manager import manager

logger = logging.getLogger(__name__)


async def create_linkedin_notification(
    user_id: str,
    title: str,
    message: str,
    reference_id: str,
    reference_type: str = "lead",
    type_name: str = "linkedin_accept"
) -> dict[str, Any]:
    """
    Creates a notification record in MongoDB and broadcasts it to the user's active WebSockets.
    """
    db = await get_database()
    now = datetime.now(timezone.utc)
    
    notif_id = str(uuid4())
    notif_doc = {
        "id": notif_id,
        "user_id": user_id,
        "sender_id": None,
        "type": type_name,
        "title": title,
        "message": message,
        "reference_id": reference_id,
        "reference_type": reference_type,
        "is_read": False,
        "created_at": now,
    }
    
    # Insert notification record
    await db.notifications.insert_one({**notif_doc, "_id": notif_id})
    logger.info("Notification created for user %s: %s", user_id, title)

    # Broadcast via WebSocket manager
    try:
        await manager.send_to_user(user_id, {
            "type": "linkedin_notification",
            "data": {
                "id": notif_id,
                "type": type_name,
                "title": title,
                "message": message,
                "reference_id": reference_id,
                "reference_type": reference_type,
                "created_at": now.isoformat()
            }
        })
    except Exception as ws_exc:
        logger.warning("Failed to broadcast notification via WebSocket: %s", ws_exc)

    return notif_doc
