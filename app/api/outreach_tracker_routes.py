"""
Outreach Tracker API Routes — /api/outreach-tracker

Full-featured lead tracking board API:
- Paginated, filterable, sortable lead list with 13 checkbox columns
- Bulk checkbox updates with auto-timeline events
- Per-lead timeline CRUD
- Team progress aggregation for manager view
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.auth.dependencies import get_current_user, get_manager_user, get_admin_user
from app.config.mongodb_config import get_database
from app.services.outreach_tracker_service import (
    CHECKBOX_FIELDS,
    get_team_progress,
    get_timeline,
    log_timeline_event,
    update_checkboxes,
)
from app.auth.password import hash_password
from app.utils.id_generator import generate_id

router = APIRouter(prefix="/outreach-tracker", tags=["Outreach Tracker"])


# ─────────────────────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────────────────────


class CheckboxUpdateRequest(BaseModel):
    updates: dict[str, Any]
    """Dict of field_name → value. Booleans for checkboxes, strings for notes/focus/assigned_user."""


class TimelineEventRequest(BaseModel):
    event_type: str
    description: str
    metadata: dict[str, Any] = {}


class UserUpdateRequest(BaseModel):
    name: str | None = None
    display_name: str | None = None
    email: str | None = None
    role: str | None = None


class UserCreateRequest(BaseModel):
    name: str
    display_name: str | None = None
    email: str
    password: str = "Welcome123!"
    role: str = "member"


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────


@router.get("")
async def get_tracker_leads(
    campaign_id: str | None = Query(None),
    assigned_user: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    sort_by: str = Query("last_activity_at"),
    sort_dir: int = Query(-1, ge=-1, le=1),
    current_user: dict = Depends(get_current_user),
):
    """
    Paginated list of leads for the Outreach Tracker board.

    Members see only their own leads. Managers/Admins see all leads.
    """
    db = await get_database()

    user_role = current_user.get("role", "member")
    
    # 1. Build core filters
    core_filters: dict[str, Any] = {}
    if campaign_id:
        core_filters["campaign_id"] = campaign_id
    if status_filter:
        core_filters["status"] = status_filter
    if search:
        core_filters["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"email": {"$regex": search, "$options": "i"}},
            {"company": {"$regex": search, "$options": "i"}},
        ]

    # 2. Build assigned user/tab filter
    assigned_user_filter: dict[str, Any] = {}
    if assigned_user:
        target_user = await db.users.find_one({
            "$or": [
                {"display_name": assigned_user},
                {"name": assigned_user}
            ]
        })
        if target_user:
            assigned_user_filter["$or"] = [
                {"assigned_user": assigned_user},
                {"user_id": target_user["id"]}
            ]
        else:
            assigned_user_filter["assigned_user"] = assigned_user

    # 3. Build filter query — all users see all leads
    # Visibility is controlled by the assigned_user tab filter, not by RBAC scoping.
    # This ensures cross-user leads (e.g. Komalpreet's leads) appear for the whole team.
    filter_query: dict[str, Any] = {}
    and_clauses = []
    if core_filters:
        and_clauses.append(core_filters)
    if assigned_user_filter:
        and_clauses.append(assigned_user_filter)

    if len(and_clauses) > 1:
        filter_query = {"$and": and_clauses}
    elif len(and_clauses) == 1:
        filter_query = and_clauses[0]
    else:
        filter_query = {}

    total = await db.leads.count_documents(filter_query)
    skip = (page - 1) * page_size

    valid_sort_fields = {
        "last_activity_at", "name", "email", "company", "status",
        "created_at", "updated_at", "next_followup_at",
    }
    if sort_by not in valid_sort_fields:
        sort_by = "last_activity_at"

    leads_cursor = (
        db.leads.find(filter_query)
        .sort(sort_by, sort_dir)
        .skip(skip)
        .limit(page_size)
    )
    leads = await leads_cursor.to_list(length=page_size)
    for lead in leads:
        lead.pop("_id", None)

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": math.ceil(total / page_size) if total > 0 else 1,
        "leads": leads,
    }



@router.get("/team-progress")
async def team_progress(
    campaign_id: str | None = Query(None),
    current_user: dict = Depends(get_current_user),
):
    """
    Aggregate outreach milestone completion stats per team member.
    """
    return await get_team_progress(campaign_id=campaign_id)


@router.get("/fields")
async def get_checkbox_fields(current_user: dict = Depends(get_current_user)):
    """Return the list of all valid checkbox field names (useful for the frontend column picker)."""
    return {"checkbox_fields": sorted(CHECKBOX_FIELDS)}


@router.get("/users")
async def get_all_users(current_user: dict = Depends(get_current_user)):
    """Get a list of all registered users with their display names and emails."""
    db = await get_database()
    cursor = db.users.find(
        {},
        {"_id": 0, "id": 1, "name": 1, "display_name": 1, "email": 1, "role": 1}
    ).sort("display_name", 1)
    users = await cursor.to_list(length=100)
    return users


@router.post("/users", status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreateRequest,
    current_user: dict = Depends(get_admin_user),
):
    """Create a new user account (only admin can manage team members)."""
    db = await get_database()
    existing = await db.users.find_one({"email": body.email.lower().strip()})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists.",
        )

    now = datetime.now(timezone.utc)
    user_id = generate_id()
    display_name = body.display_name.strip() if body.display_name else body.name.strip()

    user_doc = {
        "id": user_id,
        "email": body.email.lower().strip(),
        "name": body.name.strip(),
        "display_name": display_name,
        "password_hash": hash_password(body.password),
        "is_active": True,
        "role": body.role,
        "created_at": now,
        "updated_at": now,
    }
    await db.users.insert_one(user_doc)
    user_doc.pop("_id", None)
    user_doc.pop("password_hash", None)
    return user_doc


@router.patch("/users/{user_id}")
async def update_user_endpoint(
    user_id: str,
    body: UserUpdateRequest,
    current_user: dict = Depends(get_admin_user),
):
    """Update a user's details (only admin can manage team members)."""
    db = await get_database()
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    updates: dict[str, Any] = {}
    if body.name is not None:
        updates["name"] = body.name.strip()
    if body.display_name is not None:
        updates["display_name"] = body.display_name.strip()
    if body.email is not None:
        email_clean = body.email.lower().strip()
        existing = await db.users.find_one({"email": email_clean, "id": {"$ne": user_id}})
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email is already in use by another user.",
            )
        updates["email"] = email_clean
    if body.role is not None:
        updates["role"] = body.role

    if updates:
        updates["updated_at"] = datetime.now(timezone.utc)
        await db.users.update_one({"id": user_id}, {"$set": updates})

    updated_user = await db.users.find_one({"id": user_id})
    updated_user.pop("_id", None)
    updated_user.pop("password_hash", None)
    return updated_user


@router.delete("/users/{user_id}")
async def delete_user_endpoint(
    user_id: str,
    current_user: dict = Depends(get_admin_user),
):
    """Delete a team user account (only admin can manage team members)."""
    db = await get_database()
    if user_id == current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own account.",
        )

    res = await db.users.delete_one({"id": user_id})
    if res.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )
    return {"message": "User deleted successfully."}




@router.get("/{lead_id}")
async def get_tracker_lead(
    lead_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get a single lead by ID for the tracker timeline view."""
    db = await get_database()
    lead = await db.leads.find_one({"id": lead_id})
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found.")
    lead.pop("_id", None)
    return lead


@router.patch("/{lead_id}/checkboxes")
async def update_lead_checkboxes(
    lead_id: str,
    body: CheckboxUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Update one or more tracking checkbox fields for a lead.
    Also accepts: notes, next_followup_at, assigned_user, focus.

    Creates a timeline event for each changed checkbox and triggers Sheet sync.
    """
    if not body.updates:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="updates must be non-empty.",
        )

    try:
        updated = await update_checkboxes(
            lead_id=lead_id,
            user_id=current_user["id"],
            updates=body.updates,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return updated


@router.get("/{lead_id}/timeline")
async def get_lead_timeline(
    lead_id: str,
    limit: int = Query(100, ge=1, le=500),
    current_user: dict = Depends(get_current_user),
):
    """Return the activity timeline for a lead, newest first."""
    return await get_timeline(lead_id=lead_id, limit=limit)


@router.post("/{lead_id}/timeline", status_code=status.HTTP_201_CREATED)
async def add_timeline_event(
    lead_id: str,
    body: TimelineEventRequest,
    current_user: dict = Depends(get_current_user),
):
    """Manually log a custom timeline event for a lead."""
    try:
        event = await log_timeline_event(
            lead_id=lead_id,
            user_id=current_user["id"],
            event_type=body.event_type,
            description=body.description,
            metadata=body.metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return event


@router.post("/sync/pull")
async def trigger_pull_sync(current_user: dict = Depends(get_current_user)):
    """Pull updates from Google Sheets for the current user."""
    from app.services.sheets_sync_service import pull_sheet_updates
    try:
        count = await pull_sheet_updates(current_user["id"])
        return {"message": f"Successfully pulled {count} leads from Google Sheets."}
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.post("/sync/push")
async def trigger_push_sync(
    campaign_id: str | None = Query(None),
    current_user: dict = Depends(get_current_user),
):
    """Push leads to Google Sheets."""
    from app.services.sheets_sync_service import push_bulk
    db = await get_database()
    if not campaign_id:
        # Find first campaign or lead
        first = await db.leads.find_one({"user_id": current_user["id"]})
        campaign_id = first.get("campaign_id", "") if first else ""
    if not campaign_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No campaigns or leads found to sync.",
        )
    try:
        count = await push_bulk(campaign_id, current_user["id"])
        return {"message": f"Successfully pushed {count} leads to Google Sheets."}
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


