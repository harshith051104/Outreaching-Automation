"""
Pydantic schemas for lead management endpoints.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, EmailStr, Field


class LeadCreate(BaseModel):
    """Single lead creation payload."""
    name: str = Field(..., min_length=1, max_length=200)
    email: EmailStr
    company: str = ""
    website: str = ""
    role: str = ""
    focus: str = ""
    campaign_id: str


class LeadUpdate(BaseModel):
    """PATCH /api/leads/{id} – all fields optional."""
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    company: Optional[str] = None
    website: Optional[str] = None
    role: Optional[str] = None
    focus: Optional[str] = None
    status: Optional[str] = None
    score: Optional[float] = None
    research_data: Optional[dict[str, Any]] = None
    personalization_data: Optional[dict[str, Any]] = None


class LeadResponse(BaseModel):
    """Full lead representation returned by the API."""
    id: str
    campaign_id: str
    user_id: str
    name: str
    email: str
    company: str
    website: str
    role: str
    focus: str = ""
    status: str
    score: float
    research_data: dict[str, Any]
    personalization_data: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class LeadBulkUpload(BaseModel):
    """Bulk lead import payload."""
    campaign_id: str
    leads: list[LeadCreate]