"""
Pydantic schemas for Task Tracker and Suggestion Box.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional
from pydantic import BaseModel, Field


# ── Tasks ─────────────────────────────────────────────────────────────────

class TaskCreate(BaseModel):
    """POST /api/tasks request body."""
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = ""
    status: str = Field("todo", pattern="^(todo|in_progress|review|completed|blocked)$")
    priority: str = Field("medium", pattern="^(low|medium|high|critical)$")
    due_date: Optional[datetime] = None
    assigned_to: Optional[str] = None


class TaskUpdate(BaseModel):
    """PUT /api/tasks/{task_id} request body."""
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = Field(None, pattern="^(todo|in_progress|review|completed|blocked)$")
    priority: Optional[str] = Field(None, pattern="^(low|medium|high|critical)$")
    due_date: Optional[datetime] = None
    assigned_to: Optional[str] = None


class UserMinResponse(BaseModel):
    """Minimal user profile information."""
    id: str
    name: str
    email: str


class TaskResponse(BaseModel):
    """Task API response."""
    id: str
    user_id: str
    title: str
    description: str
    status: str
    priority: str
    due_date: Optional[datetime]
    assigned_to: Optional[str]
    assignee_info: Optional[UserMinResponse] = None
    creator_info: Optional[UserMinResponse] = None
    created_at: datetime
    updated_at: datetime


# ── Task Comments ─────────────────────────────────────────────────────────

class TaskCommentCreate(BaseModel):
    """POST /api/task-comments request body."""
    message: str = Field(..., min_length=1, max_length=1000)


class TaskCommentResponse(BaseModel):
    """Task Comment API response."""
    id: str
    task_id: str
    user_id: str
    author_info: Optional[UserMinResponse] = None
    message: str
    created_at: datetime


# ── Suggestions ───────────────────────────────────────────────────────────

class SuggestionCreate(BaseModel):
    """POST /api/suggestions request body."""
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1, max_length=2000)
    category: str = Field(..., pattern="^(suggestion|feature_request|improvement|feedback|bug_report)$")
    anonymous: bool = False
    
    # Global feedback widget metadata
    submitted_from: str = "page"
    page_name: Optional[str] = None
    page_url: Optional[str] = None
    screenshot_url: Optional[str] = None
    has_screenshot: bool = False
    browser_info: Optional[str] = None


class SuggestionStatusUpdate(BaseModel):
    """PATCH /api/suggestions/{id}/status request body."""
    status: str = Field(..., pattern="^(pending|under_review|accepted|rejected|implemented)$")


class SuggestionResponse(BaseModel):
    """Suggestion API response."""
    id: str
    user_id: Optional[str]
    author_info: Optional[UserMinResponse] = None
    title: str
    description: str
    category: str
    anonymous: bool
    status: str
    votes: List[str]
    created_at: datetime
    updated_at: datetime

    # Global feedback widget metadata
    submitted_from: str = "page"
    page_name: Optional[str] = None
    page_url: Optional[str] = None
    screenshot_url: Optional[str] = None
    has_screenshot: bool = False
    browser_info: Optional[str] = None

    # AI analysis metadata
    ai_summary: Optional[str] = None
    ai_priority: Optional[str] = None
    ai_business_impact: Optional[str] = None
    ai_suggested_category: Optional[str] = None


# ── Notifications ─────────────────────────────────────────────────────────

class NotificationResponse(BaseModel):
    """Notification API response."""
    id: str
    user_id: str
    sender_id: Optional[str]
    sender_info: Optional[UserMinResponse] = None
    type: str
    title: str
    message: str
    reference_id: str
    reference_type: str
    is_read: bool
    created_at: datetime


# ── Dashboard Stats ───────────────────────────────────────────────────────

class DashboardStatsResponse(BaseModel):
    """Dashboard statistics and activity feed."""
    total_tasks: int
    pending_tasks: int
    completed_tasks: int
    overdue_tasks: int
    total_suggestions: int
    recent_activity: List[dict]
