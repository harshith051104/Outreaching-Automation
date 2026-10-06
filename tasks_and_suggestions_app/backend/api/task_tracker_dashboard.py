"""
Task Tracker & Suggestion Box Dashboard API routes.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from app.auth.dependencies import get_current_user
from app.config.mongodb_config import get_database
from app.models.activity_log import ActivityLog
from app.schemas.task_tracker import DashboardStatsResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard", tags=["Task Tracker Dashboard"])


@router.get(
    "/stats",
    response_model=DashboardStatsResponse,
    summary="Get Task Tracker & Suggestion Box stats and timeline",
)
async def get_stats(
    current_user: dict = Depends(get_current_user),
):
    db = await get_database()
    now = datetime.now(timezone.utc)

    # 1. Total Tasks
    total_tasks = await db.tasks.count_documents({})

    # 2. Pending Tasks
    pending_tasks = await db.tasks.count_documents({
        "status": {"$in": ["todo", "in_progress", "review", "blocked"]}
    })

    # 3. Completed Tasks
    completed_tasks = await db.tasks.count_documents({"status": "completed"})

    # 4. Overdue Tasks
    overdue_tasks = await db.tasks.count_documents({
        "status": {"$in": ["todo", "in_progress", "review", "blocked"]},
        "due_date": {"$lt": now}
    })

    # 5. Total Suggestions
    total_suggestions = await db.suggestions.count_documents({})

    # 6. Recent Activity Log Timeline
    cursor = db.activity_logs.find({}).sort("created_at", -1).limit(15)
    activities = await cursor.to_list(length=15)

    recent_activity = []
    for a in activities:
        log_model = ActivityLog.from_dict(a)
        recent_activity.append({
            "id": log_model.id,
            "user_id": log_model.user_id,
            "user_name": log_model.user_name,
            "action": log_model.action,
            "reference_id": log_model.reference_id,
            "reference_type": log_model.reference_type,
            "details": log_model.details,
            "created_at": log_model.created_at.isoformat()
        })

    return {
        "total_tasks": total_tasks,
        "pending_tasks": pending_tasks,
        "completed_tasks": completed_tasks,
        "overdue_tasks": overdue_tasks,
        "total_suggestions": total_suggestions,
        "recent_activity": recent_activity
    }
