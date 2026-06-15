"""
Task Tracker API routes.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth.dependencies import get_current_user
from app.config.mongodb_config import get_database
from app.models.task import Task
from app.models.notification import Notification
from app.models.activity_log import ActivityLog
from app.schemas.task_tracker import TaskCreate, TaskUpdate, TaskResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tasks", tags=["Task Tracker"])


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


@router.post(
    "",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new task",
)
async def create(
    data: TaskCreate,
    current_user: dict = Depends(get_current_user),
):
    db = await get_database()
    now = datetime.now(timezone.utc)

    task_obj = Task(
        user_id=current_user["id"],
        title=data.title.strip(),
        description=data.description or "",
        status=data.status,
        priority=data.priority,
        due_date=data.due_date,
        assigned_to=data.assigned_to,
        created_at=now,
        updated_at=now,
    )

    task_dict = task_obj.to_dict()
    await db.tasks.insert_one(task_dict)

    # Activity Logging
    activity = ActivityLog(
        user_id=current_user["id"],
        user_name=current_user["name"],
        action="task_created",
        reference_id=task_obj.id,
        reference_type="task",
        details=f"Created task: '{task_obj.title}'",
    )
    await db.activity_logs.insert_one(activity.to_dict())

    # Notification for Assignee
    if task_obj.assigned_to and task_obj.assigned_to != current_user["id"]:
        notification = Notification(
            user_id=task_obj.assigned_to,
            sender_id=current_user["id"],
            type="task_assigned",
            title="New Task Assigned",
            message=f"You have been assigned to: '{task_obj.title}' by {current_user['name']}.",
            reference_id=task_obj.id,
            reference_type="task",
        )
        await db.notifications.insert_one(notification.to_dict())

    # Format response
    creator_info = await _populate_user_info(task_obj.user_id)
    assignee_info = await _populate_user_info(task_obj.assigned_to)

    res = task_obj.model_dump()
    res["creator_info"] = creator_info
    res["assignee_info"] = assignee_info
    return res


@router.get(
    "",
    response_model=List[TaskResponse],
    summary="List all tasks with optional search/filters",
)
async def list_tasks(
    status_filter: Optional[str] = Query(None, alias="status"),
    priority_filter: Optional[str] = Query(None, alias="priority"),
    assigned_to: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    db = await get_database()
    query = {}

    if status_filter:
        query["status"] = status_filter
    if priority_filter:
        query["priority"] = priority_filter
    if assigned_to:
        query["assigned_to"] = assigned_to
    if search:
        query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}},
        ]

    cursor = db.tasks.find(query).sort("created_at", -1)
    tasks_list = await cursor.to_list(length=1000)

    res_list = []
    for t in tasks_list:
        task_model = Task.from_dict(t)
        creator_info = await _populate_user_info(task_model.user_id)
        assignee_info = await _populate_user_info(task_model.assigned_to)

        task_data = task_model.model_dump()
        task_data["creator_info"] = creator_info
        task_data["assignee_info"] = assignee_info
        res_list.append(task_data)

    return res_list


@router.get(
    "/{task_id}",
    response_model=TaskResponse,
    summary="Get single task details",
)
async def get_task(
    task_id: str,
    current_user: dict = Depends(get_current_user),
):
    db = await get_database()
    task_doc = await db.tasks.find_one({"_id": task_id})
    if not task_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found.",
        )

    task_model = Task.from_dict(task_doc)
    creator_info = await _populate_user_info(task_model.user_id)
    assignee_info = await _populate_user_info(task_model.assigned_to)

    res = task_model.model_dump()
    res["creator_info"] = creator_info
    res["assignee_info"] = assignee_info
    return res


@router.put(
    "/{task_id}",
    response_model=TaskResponse,
    summary="Update an existing task",
)
async def update(
    task_id: str,
    data: TaskUpdate,
    current_user: dict = Depends(get_current_user),
):
    db = await get_database()
    task_doc = await db.tasks.find_one({"_id": task_id})
    if not task_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found.",
        )

    task_model = Task.from_dict(task_doc)
    now = datetime.now(timezone.utc)

    # Detect changes for activity logs/notifications
    old_status = task_model.status
    old_assignee = task_model.assigned_to

    update_dict = data.model_dump(exclude_unset=True)
    if "status" in update_dict:
        task_model.status = update_dict["status"]
    if "title" in update_dict:
        task_model.title = update_dict["title"]
    if "description" in update_dict:
        task_model.description = update_dict["description"]
    if "priority" in update_dict:
        task_model.priority = update_dict["priority"]
    if "due_date" in update_dict:
        task_model.due_date = update_dict["due_date"]
    if "assigned_to" in update_dict:
        task_model.assigned_to = update_dict["assigned_to"]

    task_model.updated_at = now

    await db.tasks.replace_one({"_id": task_id}, task_model.to_dict())

    # Logs activity log details
    activity_details = []
    if old_status != task_model.status:
        activity_details.append(f"changed status from '{old_status}' to '{task_model.status}'")
        
        # Notify creator if completed by assignee
        if task_model.status == "completed" and task_model.user_id != current_user["id"]:
            notification = Notification(
                user_id=task_model.user_id,
                sender_id=current_user["id"],
                type="task_completed",
                title="Task Completed",
                message=f"Task '{task_model.title}' has been completed by {current_user['name']}.",
                reference_id=task_model.id,
                reference_type="task",
            )
            await db.notifications.insert_one(notification.to_dict())

    if old_assignee != task_model.assigned_to:
        activity_details.append("reassigned task")
        # Notify new assignee
        if task_model.assigned_to and task_model.assigned_to != current_user["id"]:
            notification = Notification(
                user_id=task_model.assigned_to,
                sender_id=current_user["id"],
                type="task_assigned",
                title="New Task Assigned",
                message=f"You have been assigned to: '{task_model.title}' by {current_user['name']}.",
                reference_id=task_model.id,
                reference_type="task",
            )
            await db.notifications.insert_one(notification.to_dict())

    if not activity_details:
        activity_details.append("updated task properties")

    activity = ActivityLog(
        user_id=current_user["id"],
        user_name=current_user["name"],
        action="task_updated",
        reference_id=task_model.id,
        reference_type="task",
        details=f"Updated task '{task_model.title}': {', '.join(activity_details)}",
    )
    await db.activity_logs.insert_one(activity.to_dict())

    creator_info = await _populate_user_info(task_model.user_id)
    assignee_info = await _populate_user_info(task_model.assigned_to)

    res = task_model.model_dump()
    res["creator_info"] = creator_info
    res["assignee_info"] = assignee_info
    return res


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a task",
)
async def delete_task(
    task_id: str,
    current_user: dict = Depends(get_current_user),
):
    db = await get_database()
    task_doc = await db.tasks.find_one({"_id": task_id})
    if not task_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found.",
        )

    task_model = Task.from_dict(task_doc)
    await db.tasks.delete_one({"_id": task_id})

    # Log deletion
    activity = ActivityLog(
        user_id=current_user["id"],
        user_name=current_user["name"],
        action="task_deleted",
        reference_id=task_id,
        reference_type="task",
        details=f"Deleted task '{task_model.title}'",
    )
    await db.activity_logs.insert_one(activity.to_dict())

    # Delete related task comments
    await db.task_comments.delete_many({"task_id": task_id})

    return None


@router.post(
    "/export/sheets",
    summary="Export filtered tasks to Google Sheets",
)
async def export_tasks_to_sheets(
    status_filter: Optional[str] = Query(None, alias="status"),
    priority_filter: Optional[str] = Query(None, alias="priority"),
    assigned_to: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    db = await get_database()
    query = {}

    if status_filter:
        query["status"] = status_filter
    if priority_filter:
        query["priority"] = priority_filter
    if assigned_to:
        query["assigned_to"] = assigned_to
    if search:
        query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}},
        ]

    cursor = db.tasks.find(query).sort("created_at", -1)
    tasks_list = await cursor.to_list(length=1000)

    headers = [
        "Task ID",
        "Title",
        "Description",
        "Status",
        "Priority",
        "Creator Name",
        "Assignee Name",
        "Due Date",
        "Created At"
    ]

    rows = []
    for t in tasks_list:
        task_model = Task.from_dict(t)
        creator_info = await _populate_user_info(task_model.user_id)
        assignee_info = await _populate_user_info(task_model.assigned_to)

        creator_name = creator_info.get("name") if creator_info else "System"
        assignee_name = assignee_info.get("name") if assignee_info else "Unassigned"

        due_date_str = task_model.due_date.strftime("%Y-%m-%d") if task_model.due_date else "No due date"
        created_at_str = task_model.created_at.strftime("%Y-%m-%d %H:%M") if task_model.created_at else ""

        rows.append([
            task_model.id,
            task_model.title,
            task_model.description,
            task_model.status,
            task_model.priority,
            creator_name,
            assignee_name,
            due_date_str,
            created_at_str
        ])

    from app.services.google_sheets_service import create_and_fill_spreadsheet
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    return await create_and_fill_spreadsheet(
        user_id=current_user["id"],
        title=f"Outreach Tasks List - {now_str}",
        headers=headers,
        rows=rows
    )

