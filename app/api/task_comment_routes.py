"""
Task Comment API routes.
"""

import logging
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.dependencies import get_current_user
from app.config.mongodb_config import get_database
from app.models.task_comment import TaskComment
from app.models.notification import Notification
from app.models.activity_log import ActivityLog
from app.schemas.task_tracker import TaskCommentCreate, TaskCommentResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/task-comments", tags=["Task Tracker"])


async def _populate_user_info(user_id: str | None) -> dict | None:
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


@router.post(
    "/{task_id}",
    response_model=TaskCommentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a comment to a task",
)
async def add_comment(
    task_id: str,
    data: TaskCommentCreate,
    current_user: dict = Depends(get_current_user),
):
    db = await get_database()
    
    # Verify task exists
    task_doc = await db.tasks.find_one({"_id": task_id})
    if not task_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found.",
        )

    comment = TaskComment(
        task_id=task_id,
        user_id=current_user["id"],
        message=data.message.strip(),
        created_at=datetime.now(timezone.utc),
    )

    await db.task_comments.insert_one(comment.to_dict())

    # Create Activity Log
    activity = ActivityLog(
        user_id=current_user["id"],
        user_name=current_user["name"],
        action="comment_added",
        reference_id=task_id,
        reference_type="task",
        details=f"Commented on task: '{task_doc.get('title')}'",
    )
    await db.activity_logs.insert_one(activity.to_dict())

    # Send Notification to Creator and/or Assignee
    task_creator = task_doc.get("user_id")
    task_assignee = task_doc.get("assigned_to")

    notified_users = set()
    if task_creator and task_creator != current_user["id"]:
        notified_users.add(task_creator)
    if task_assignee and task_assignee != current_user["id"]:
        notified_users.add(task_assignee)

    for user_to_notify in notified_users:
        notification = Notification(
            user_id=user_to_notify,
            sender_id=current_user["id"],
            type="comment_added",
            title="New Comment on Task",
            message=f"{current_user['name']} commented on: '{task_doc.get('title')}'",
            reference_id=task_id,
            reference_type="task",
        )
        await db.notifications.insert_one(notification.to_dict())

    author_info = await _populate_user_info(comment.user_id)
    res = comment.model_dump()
    res["author_info"] = author_info
    return res


@router.get(
    "/{task_id}",
    response_model=List[TaskCommentResponse],
    summary="Get comments for a task",
)
async def list_comments(
    task_id: str,
    current_user: dict = Depends(get_current_user),
):
    db = await get_database()
    
    cursor = db.task_comments.find({"task_id": task_id}).sort("created_at", 1)
    comments_list = await cursor.to_list(length=100)

    res_list = []
    for c in comments_list:
        comment_model = TaskComment.from_dict(c)
        author_info = await _populate_user_info(comment_model.user_id)

        comment_data = comment_model.model_dump()
        comment_data["author_info"] = author_info
        res_list.append(comment_data)

    return res_list
