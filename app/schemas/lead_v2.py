"""
Pydantic schemas for lead management endpoints.

Enhanced to support Instantly-style workflows:
- Lead lists for organizing contacts
- Lead labels/tags for categorization
- Interest status tracking
- Bulk import with validation
- Lead merging and moving between campaigns/lists
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, EmailStr, Field


# ── Enums ──────────────────────────────────────────────────────────────────


class LeadStatus(str, Enum):
    NEW = "new"
    CONTACTED = "contacted"
    OPENED = "opened"
    CLICKED = "clicked"
    REPLIED = "replied"
    INTERESTED = "interested"
    MEETING_BOOKED = "meeting_booked"
    MEETING_COMPLETED = "meeting_completed"
    CLOSED_WON = "closed_won"
    CLOSED_LOST = "closed_lost"
    UNSUBSCRIBED = "unsubscribed"
    BOUNCED = "bounced"
    WRONG_PERSON = "wrong_person"
    OUT_OF_OFFICE = "out_of_office"


class InterestStatus(str, Enum):
    NEUTRAL = "neutral"
    INTERESTED = "interested"
    NOT_INTERESTED = "not_interested"
    MEETING_BOOKED = "meeting_booked"
    MEETING_COMPLETED = "meeting_completed"
    CLOSED = "closed"
    OUT_OF_OFFICE = "out_of_office"
    WRONG_PERSON = "wrong_person"


class LeadSource(str, Enum):
    CSV = "csv"
    MANUAL = "manual"
    API = "api"
    SUPERSEARCH = "supersearch"
    ENRICHMENT = "enrichment"
    WEBSITE = "website"


# ── Lead Lists ─────────────────────────────────────────────────────────────


class LeadListCreate(BaseModel):
    """Create a new lead list."""
    name: str = Field(..., min_length=1, max_length=200)
    description: str = ""


class LeadListUpdate(BaseModel):
    """Update a lead list."""
    name: Optional[str] = None
    description: Optional[str] = None


class LeadListResponse(BaseModel):
    """Lead list with stats."""
    id: str
    user_id: str
    name: str
    description: str
    total_leads: int = 0
    created_at: datetime
    updated_at: datetime


# ── Lead Labels ────────────────────────────────────────────────────────────


class LeadLabelCreate(BaseModel):
    """Create a custom lead label."""
    name: str = Field(..., min_length=1, max_length=100)
    color: str = Field(default="#3B82F6", description="Hex color code")
    description: str = ""


class LeadLabelResponse(BaseModel):
    """Lead label representation."""
    id: str
    user_id: str
    name: str
    color: str
    description: str
    created_at: datetime


# ── Lead CRUD ──────────────────────────────────────────────────────────────


class LeadCreate(BaseModel):
    """Single lead creation payload."""
    name: str = Field(..., min_length=1, max_length=200)
    email: EmailStr
    company: str = ""
    website: str = ""
    role: str = ""
    phone: str = ""
    linkedin_url: str = ""
    campaign_id: str = ""
    list_id: Optional[str] = None
    labels: list[str] = Field(default_factory=list, description="Label IDs")
    custom_fields: dict[str, Any] = Field(default_factory=dict)
    source: LeadSource = LeadSource.MANUAL


class LeadUpdate(BaseModel):
    """PATCH /api/leads/{id} – all fields optional."""
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    company: Optional[str] = None
    website: Optional[str] = None
    role: Optional[str] = None
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    status: Optional[LeadStatus] = None
    interest_status: Optional[InterestStatus] = None
    score: Optional[float] = None
    labels: Optional[list[str]] = None
    custom_fields: Optional[dict[str, Any]] = None
    research_data: Optional[dict[str, Any]] = None
    personalization_data: Optional[dict[str, Any]] = None


class LeadResponse(BaseModel):
    """Full lead representation returned by the API."""
    id: str
    campaign_id: str
    list_id: Optional[str] = None
    user_id: str
    name: str
    email: str
    company: str
    website: str
    role: str
    phone: str
    linkedin_url: str
    status: LeadStatus
    interest_status: InterestStatus
    score: float
    labels: list[str] = Field(default_factory=list)
    custom_fields: dict[str, Any] = Field(default_factory=dict)
    source: LeadSource
    research_data: dict[str, Any] = Field(default_factory=dict)
    personalization_data: dict[str, Any] = Field(default_factory=dict)
    engagement_score: float = 0.0
    last_contacted_at: Optional[datetime] = None
    last_replied_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class LeadBulkUpload(BaseModel):
    """Bulk lead import payload."""
    campaign_id: str = ""
    list_id: Optional[str] = None
    leads: list[LeadCreate] = Field(..., min_length=1, max_length=1000)
    skip_duplicates: bool = True
    labels: list[str] = Field(default_factory=list, description="Apply labels to all imported leads")


class LeadBulkImportResponse(BaseModel):
    """Response for bulk lead import."""
    total_submitted: int
    total_imported: int
    total_skipped: int
    duplicates: list[str] = Field(default_factory=list)
    errors: list[dict[str, Any]] = Field(default_factory=list)


# ── Lead Assignment ────────────────────────────────────────────────────────


class LeadAssignRequest(BaseModel):
    """Assign leads to a user."""
    lead_ids: list[str] = Field(..., min_length=1)
    user_id: str


# ── Lead Move ──────────────────────────────────────────────────────────────


class LeadMoveRequest(BaseModel):
    """Move leads between campaigns or lists."""
    lead_ids: list[str] = Field(..., min_length=1)
    target_campaign_id: Optional[str] = None
    target_list_id: Optional[str] = None


# ── Lead Merge ─────────────────────────────────────────────────────────────


class LeadMergeRequest(BaseModel):
    """Merge two leads into one."""
    primary_lead_id: str
    secondary_lead_id: str


# ── Block List ─────────────────────────────────────────────────────────────


class BlockListEntryCreate(BaseModel):
    """Block an email or domain."""
    value: str = Field(..., description="Email address or domain to block")
    reason: str = ""


class BlockListEntryResponse(BaseModel):
    """Block list entry representation."""
    id: str
    user_id: str
    value: str
    reason: str
    created_at: datetime


# ── Email Verification ─────────────────────────────────────────────────────


class EmailVerificationRequest(BaseModel):
    """Verify an email address."""
    email: EmailStr


class EmailVerificationResponse(BaseModel):
    """Email verification result."""
    email: str
    is_valid: bool
    is_disposable: bool
    is_role_account: bool
    mx_found: bool
    smtp_check: bool
    risk_score: float
    status: str  # valid, invalid, risky, unknown
