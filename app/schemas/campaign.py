"""
Pydantic schemas for campaign CRUD operations.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class CampaignSettings(BaseModel):
    """Nested settings object for a campaign."""
    max_emails_per_day: int = 50
    delay_between_emails_seconds: int = 60
    follow_up_count: int = 3
    follow_up_delay_hours: int = 48
    tone: str = "professional"
    timezone: str = "UTC"


class CampaignCreate(BaseModel):
    """POST /api/campaigns request body."""
    name: str = Field(..., min_length=1, max_length=300)
    description: str = ""
    subject_template: str = ""
    body_template: str = ""
    gmail_account_id: str = ""
    settings: CampaignSettings = Field(default_factory=CampaignSettings)
    sequence_steps: Optional[list[dict[str, Any]]] = None


class CampaignUpdate(BaseModel):
    """PATCH /api/campaigns/{id} request body – all fields optional."""
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    subject_template: Optional[str] = None
    body_template: Optional[str] = None
    gmail_account_id: Optional[str] = None
    settings: Optional[CampaignSettings] = None
    sequence_steps: Optional[list[dict[str, Any]]] = None


class CampaignResponse(BaseModel):
    """Full campaign representation returned by the API."""
    id: str
    user_id: str
    name: str
    description: str
    status: str
    subject_template: str
    body_template: str
    gmail_account_id: str
    settings: dict[str, Any]
    total_leads: int
    sent_count: int
    sequence_steps: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime