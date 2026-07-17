"""
MongoDB persistence for dashboard data.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


async def _get_db():
    from app.config.mongodb_config import get_database
    return await get_database()


async def save_activity_log(doc: Dict[str, Any]) -> bool:
    """Save an activity log entry."""
    try:
        db = await _get_db()
        await db.activity_logs.insert_one(doc)
        return True
    except Exception as exc:
        logger.error("Failed to save activity log: %s", exc)
        return False


async def save_notification(doc: Dict[str, Any]) -> bool:
    """Save a notification."""
    try:
        db = await _get_db()
        await db.notifications.insert_one(doc)
        return True
    except Exception as exc:
        logger.error("Failed to save notification: %s", exc)
        return False


async def save_execution_log(doc: Dict[str, Any]) -> bool:
    """Save an execution log entry."""
    try:
        db = await _get_db()
        if hasattr(db, "execution_logs"):
            await db.execution_logs.insert_one(doc)
        return True
    except Exception as exc:
        logger.error("Failed to save execution log: %s", exc)
        return False


async def get_recent_events(user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Get recent events for a user."""
    try:
        db = await _get_db()
        cursor = db.activity_logs.find(
            {"user_id": user_id}
        ).sort("created_at", -1).limit(limit)
        return await cursor.to_list(length=limit)
    except Exception:
        return []
