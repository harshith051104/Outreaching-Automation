"""
Notification API routes.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth.dependencies import get_current_user
from app.config.mongodb_config import get_database
from app.models.notification import Notification
from app.schemas.task_tracker import NotificationResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications", tags=["Notifications"])


async def _populate_user_info(user_id: str | None) -> Optional[dict]:
    if not user_id:
        return None
    try:
        from app.services.auth_service import get_user_by_id
        user = await get_user_by_id(user_id)
        return {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"]
        }
    except Exception:
        return None


@router.get(
    "",
    response_model=List[NotificationResponse],
    summary="List all notifications for current user",
)
async def list_notifications(
    unread_only: bool = Query(False, alias="unreadOnly"),
    current_user: dict = Depends(get_current_user),
):
    db = await get_database()
    query = {"user_id": current_user["id"]}

    if unread_only:
        query["is_read"] = False

    cursor = db.notifications.find(query).sort("created_at", -1)
    notifs_list = await cursor.to_list(length=100)

    res_list = []
    for n in notifs_list:
        try:
            # Coerce fields to prevent Pydantic validation failures on old documents
            if "_id" in n:
                n["id"] = str(n.pop("_id"))
            elif "id" in n:
                n["id"] = str(n["id"])
                
            if "reference_id" not in n:
                n["reference_id"] = ""
            if "reference_type" not in n:
                n["reference_type"] = ""
            if "is_read" not in n:
                n["is_read"] = False

            notif_model = Notification.from_dict(n)
            sender_info = await _populate_user_info(notif_model.sender_id)

            notif_data = notif_model.model_dump()
            notif_data["sender_info"] = sender_info
            res_list.append(notif_data)
        except Exception as e:
            logger.warning("Failed to parse notification document %s: %s", n, e)
            continue

    return res_list


@router.get(
    "/unread-count",
    summary="Get unread notification count",
)
async def get_unread_count(
    current_user: dict = Depends(get_current_user),
):
    db = await get_database()
    count = await db.notifications.count_documents({
        "user_id": current_user["id"],
        "is_read": False
    })
    return {"count": count}


@router.patch(
    "/{notification_id}/read",
    response_model=dict,
    summary="Mark single notification as read",
)
async def mark_read(
    notification_id: str,
    current_user: dict = Depends(get_current_user),
):
    db = await get_database()
    
    # Check if notification exists and belongs to current user
    notif = await db.notifications.find_one({"_id": notification_id, "user_id": current_user["id"]})
    if not notif:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found.",
        )

    await db.notifications.update_one(
        {"_id": notification_id},
        {"$set": {"is_read": True}}
    )
    return {"status": "success", "message": "Notification marked as read."}


@router.post(
    "/read-all",
    response_model=dict,
    summary="Mark all notifications as read",
)
async def mark_all_read(
    current_user: dict = Depends(get_current_user),
):
    db = await get_database()
    result = await db.notifications.update_many(
        {"user_id": current_user["id"], "is_read": False},
        {"$set": {"is_read": True}}
    )
    return {
        "status": "success",
        "message": f"All notifications marked as read. Modified {result.modified_count} items."
    }


@router.delete(
    "",
    response_model=dict,
    summary="Delete all notifications for current user",
)
async def delete_all(
    current_user: dict = Depends(get_current_user),
):
    db = await get_database()
    result = await db.notifications.delete_many({"user_id": current_user["id"]})
    return {
        "status": "success",
        "message": f"Deleted {result.deleted_count} notifications."
    }
