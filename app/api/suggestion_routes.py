"""
Suggestion Box API routes.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.config.mongodb_config import get_database
from app.models.suggestion import Suggestion
from app.models.notification import Notification
from app.models.activity_log import ActivityLog
from app.schemas.task_tracker import (
    SuggestionCreate,
    SuggestionStatusUpdate,
    SuggestionResponse,
    UserMinResponse,
)
from app.services.suggestion_ai_service import enhance_suggestion_with_ai

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/suggestions", tags=["Suggestion Box"])


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


# ── REST endpoints ─────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=SuggestionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a new suggestion",
)
async def create(
    data: SuggestionCreate,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    db = await get_database()
    now = datetime.now(timezone.utc)

    user_id = None if data.anonymous else current_user["id"]

    suggestion_obj = Suggestion(
        user_id=user_id,
        title=data.title.strip(),
        description=data.description.strip(),
        category=data.category,
        anonymous=data.anonymous,
        status="pending",
        votes=[],
        created_at=now,
        updated_at=now,
        # Widget and metadata fields
        submitted_from=data.submitted_from,
        page_name=data.page_name,
        page_url=data.page_url,
        screenshot_url=data.screenshot_url,
        has_screenshot=data.has_screenshot,
        browser_info=data.browser_info,
    )

    await db.suggestions.insert_one(suggestion_obj.to_dict())

    # Create Activity Log
    display_author = "Anonymous" if data.anonymous else current_user["name"]
    is_widget = data.submitted_from == "widget"
    
    activity = ActivityLog(
        user_id=current_user["id"],
        user_name=display_author,
        action="suggestion_submitted_from_widget" if is_widget else "suggestion_submitted",
        reference_id=suggestion_obj.id,
        reference_type="suggestion",
        details=f"Submitted a suggestion from widget: '{suggestion_obj.title}'" if is_widget else f"Submitted a suggestion: '{suggestion_obj.title}'",
    )
    await db.activity_logs.insert_one(activity.to_dict())

    # Notify all active users or system admins
    cursor = db.users.find({"is_active": True})
    users_list = await cursor.to_list(length=200)
    for u in users_list:
        if u["id"] != current_user["id"]:
            notification = Notification(
                user_id=u["id"],
                sender_id=user_id,
                type="suggestion_submitted",
                title="New Suggestion Submitted" if not is_widget else "New Feedback Widget Suggestion",
                message=f"A new feedback suggestion has been posted: '{suggestion_obj.title}'." if not is_widget else f"New widget suggestion: '{suggestion_obj.title}' from page '{data.page_name}'.",
                reference_id=suggestion_obj.id,
                reference_type="suggestion",
            )
            await db.notifications.insert_one(notification.to_dict())

    # Add background task for AI Enhancement
    background_tasks.add_task(enhance_suggestion_with_ai, suggestion_obj.id)

    res = suggestion_obj.model_dump()
    res["author_info"] = None if data.anonymous else await _populate_user_info(current_user["id"])
    return res


@router.get(
    "",
    response_model=List[SuggestionResponse],
    summary="List all suggestions",
)
async def list_suggestions(
    category: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    submitted_from: Optional[str] = Query(None),
    has_screenshot: Optional[bool] = Query(None),
    anonymous: Optional[bool] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    db = await get_database()
    query = {}

    if category:
        query["category"] = category
    if status_filter:
        query["status"] = status_filter
    if submitted_from:
        query["submitted_from"] = submitted_from
    if has_screenshot is not None:
        query["has_screenshot"] = has_screenshot
    if anonymous is not None:
        query["anonymous"] = anonymous

    cursor = db.suggestions.find(query).sort("created_at", -1)
    suggestions_list = await cursor.to_list(length=1000)

    res_list = []
    for s in suggestions_list:
        sug_model = Suggestion.from_dict(s)
        
        # Populate author if not anonymous
        author_info = None
        if not sug_model.anonymous and sug_model.user_id:
            author_info = await _populate_user_info(sug_model.user_id)

        sug_data = sug_model.model_dump()
        sug_data["author_info"] = author_info
        res_list.append(sug_data)

    return res_list


@router.get(
    "/{suggestion_id}",
    response_model=SuggestionResponse,
    summary="Get single suggestion details",
)
async def get_suggestion(
    suggestion_id: str,
    current_user: dict = Depends(get_current_user),
):
    db = await get_database()
    suggestion_doc = await db.suggestions.find_one({"_id": suggestion_id})
    if not suggestion_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Suggestion not found.",
        )

    sug_model = Suggestion.from_dict(suggestion_doc)
    
    author_info = None
    if not sug_model.anonymous and sug_model.user_id:
        author_info = await _populate_user_info(sug_model.user_id)

    res = sug_model.model_dump()
    res["author_info"] = author_info
    return res


@router.patch(
    "/{suggestion_id}/status",
    response_model=SuggestionResponse,
    summary="Update suggestion status (Admin)",
)
async def update_status(
    suggestion_id: str,
    data: SuggestionStatusUpdate,
    current_user: dict = Depends(get_current_user),
):
    db = await get_database()
    suggestion_doc = await db.suggestions.find_one({"_id": suggestion_id})
    if not suggestion_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Suggestion not found.",
        )

    sug_model = Suggestion.from_dict(suggestion_doc)
    old_status = sug_model.status
    sug_model.status = data.status
    sug_model.updated_at = datetime.now(timezone.utc)

    await db.suggestions.replace_one({"_id": suggestion_id}, sug_model.to_dict())

    # Create Activity Log
    activity = ActivityLog(
        user_id=current_user["id"],
        user_name=current_user["name"],
        action="suggestion_updated",
        reference_id=suggestion_id,
        reference_type="suggestion",
        details=f"Updated status of suggestion '{sug_model.title}' from '{old_status}' to '{sug_model.status}'",
    )
    await db.activity_logs.insert_one(activity.to_dict())

    # Notify author if not anonymous
    if sug_model.user_id and not sug_model.anonymous:
        notification = Notification(
            user_id=sug_model.user_id,
            sender_id=current_user["id"],
            type="suggestion_status_changed",
            title="Suggestion Status Updated",
            message=f"Your suggestion '{sug_model.title}' status has changed to '{sug_model.status}'.",
            reference_id=suggestion_id,
            reference_type="suggestion",
        )
        await db.notifications.insert_one(notification.to_dict())

    author_info = None
    if not sug_model.anonymous and sug_model.user_id:
        author_info = await _populate_user_info(sug_model.user_id)

    res = sug_model.model_dump()
    res["author_info"] = author_info
    return res


@router.post(
    "/{suggestion_id}/vote",
    response_model=SuggestionResponse,
    summary="Upvote a suggestion",
)
async def upvote(
    suggestion_id: str,
    current_user: dict = Depends(get_current_user),
):
    db = await get_database()
    suggestion_doc = await db.suggestions.find_one({"_id": suggestion_id})
    if not suggestion_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Suggestion not found.",
        )

    sug_model = Suggestion.from_dict(suggestion_doc)
    user_id = current_user["id"]

    if user_id in sug_model.votes:
        sug_model.votes.remove(user_id)  # Toggle off
    else:
        sug_model.votes.append(user_id)  # Toggle on

    sug_model.updated_at = datetime.now(timezone.utc)
    await db.suggestions.replace_one({"_id": suggestion_id}, sug_model.to_dict())

    author_info = None
    if not sug_model.anonymous and sug_model.user_id:
        author_info = await _populate_user_info(sug_model.user_id)

    res = sug_model.model_dump()
    res["author_info"] = author_info
    return res


# ── Suggestion Comments Endpoints ──────────────────────────────────────────

class SuggestionCommentCreate(BaseModel):
    message: str


class SuggestionCommentResponse(BaseModel):
    id: str
    suggestion_id: str
    user_id: str
    author_info: Optional[UserMinResponse] = None
    message: str
    created_at: datetime


@router.post(
    "/{suggestion_id}/comments",
    response_model=SuggestionCommentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a comment to a suggestion",
)
async def add_suggestion_comment(
    suggestion_id: str,
    data: SuggestionCommentCreate,
    current_user: dict = Depends(get_current_user),
):
    db = await get_database()
    
    suggestion_doc = await db.suggestions.find_one({"_id": suggestion_id})
    if not suggestion_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Suggestion not found.",
        )

    comment_id = str(uuid4())
    now = datetime.now(timezone.utc)
    
    comment_doc = {
        "_id": comment_id,
        "suggestion_id": suggestion_id,
        "user_id": current_user["id"],
        "message": data.message.strip(),
        "created_at": now
    }

    await db.suggestion_comments.insert_one(comment_doc)

    # Activity Log
    display_author = "Anonymous" if suggestion_doc.get("anonymous") else current_user["name"]
    activity = ActivityLog(
        user_id=current_user["id"],
        user_name=display_author,
        action="comment_added",
        reference_id=suggestion_id,
        reference_type="suggestion",
        details=f"Commented on suggestion: '{suggestion_doc.get('title')}'",
    )
    await db.activity_logs.insert_one(activity.to_dict())

    # Notify suggestion creator
    creator_id = suggestion_doc.get("user_id")
    if creator_id and creator_id != current_user["id"] and not suggestion_doc.get("anonymous"):
        notification = Notification(
            user_id=creator_id,
            sender_id=current_user["id"],
            type="comment_added",
            title="New Comment on Suggestion",
            message=f"{current_user['name']} commented on: '{suggestion_doc.get('title')}'",
            reference_id=suggestion_id,
            reference_type="suggestion",
        )
        await db.notifications.insert_one(notification.to_dict())

    return {
        "id": comment_id,
        "suggestion_id": suggestion_id,
        "user_id": current_user["id"],
        "author_info": await _populate_user_info(current_user["id"]),
        "message": data.message.strip(),
        "created_at": now
    }


@router.get(
    "/{suggestion_id}/comments",
    response_model=List[SuggestionCommentResponse],
    summary="Get comments for a suggestion",
)
async def list_suggestion_comments(
    suggestion_id: str,
    current_user: dict = Depends(get_current_user),
):
    db = await get_database()
    cursor = db.suggestion_comments.find({"suggestion_id": suggestion_id}).sort("created_at", 1)
    comments = await cursor.to_list(length=100)

    res_list = []
    for c in comments:
        author_info = await _populate_user_info(c["user_id"])
        res_list.append({
            "id": c["_id"],
            "suggestion_id": c["suggestion_id"],
            "user_id": c["user_id"],
            "author_info": author_info,
            "message": c["message"],
            "created_at": c["created_at"]
        })

    return res_list
