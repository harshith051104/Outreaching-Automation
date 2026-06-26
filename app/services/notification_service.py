"""
Centralized Notification Service.

Single entry point for creating in-app notifications from any module.
Stores to MongoDB and (optionally) triggers future WebSocket push.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


async def notify(
    user_id: str,
    type: str,
    title: str,
    message: str,
    reference_id: str = "",
    reference_type: str = "",
    sender_id: Optional[str] = None,
) -> None:
    """
    Create an in-app notification for a user.

    Args:
        user_id:        Recipient's user ID.
        type:           Notification category (e.g. 'campaign_started', 'email_sent').
        title:          Short notification title.
        message:        Notification body text.
        reference_id:   ID of the related object (campaign, task, email, etc.)
        reference_type: Type of the related object ('campaign', 'task', etc.)
        sender_id:      User ID of who triggered the action (optional).
    """
    try:
        from app.config.mongodb_config import get_database
        from app.models.notification import Notification

        db = await get_database()
        notif = Notification(
            user_id=user_id,
            sender_id=sender_id,
            type=type,
            title=title,
            message=message,
            reference_id=reference_id,
            reference_type=reference_type,
        )
        await db.notifications.insert_one(notif.to_dict())
        logger.debug("Notification created for user %s: [%s] %s", user_id, type, title)
    except Exception as exc:
        # Notifications are non-critical — never let them crash the caller
        logger.warning("Failed to create notification for user %s: %s", user_id, exc)


async def notify_campaign_owner(
    campaign_id: str,
    type: str,
    title: str,
    message: str,
    sender_id: Optional[str] = None,
) -> None:
    """
    Notify the owner of a campaign.
    Fetches user_id from the campaign document automatically.
    """
    try:
        from app.config.mongodb_config import get_database
        db = await get_database()
        campaign = await db.campaigns.find_one({"id": campaign_id}, {"user_id": 1})
        if campaign and campaign.get("user_id"):
            await notify(
                user_id=campaign["user_id"],
                type=type,
                title=title,
                message=message,
                reference_id=campaign_id,
                reference_type="campaign",
                sender_id=sender_id,
            )
    except Exception as exc:
        logger.warning("notify_campaign_owner failed for %s: %s", campaign_id, exc)


async def notify_all_admins(
    type: str,
    title: str,
    message: str,
    reference_id: str = "",
    reference_type: str = "",
    sender_id: Optional[str] = None,
) -> None:
    """Broadcast a notification to all admin/manager users."""
    try:
        from app.config.mongodb_config import get_database
        db = await get_database()
        admins = await db.users.find(
            {"role": {"$in": ["admin", "manager"]}}, {"id": 1}
        ).to_list(length=50)
        for admin in admins:
            if admin.get("id"):
                await notify(
                    user_id=admin["id"],
                    type=type,
                    title=title,
                    message=message,
                    reference_id=reference_id,
                    reference_type=reference_type,
                    sender_id=sender_id,
                )
    except Exception as exc:
        logger.warning("notify_all_admins failed: %s", exc)
