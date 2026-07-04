"""
Lead document model for MongoDB.

A lead is a person targeted by a campaign. It carries contact details,
AI-generated research/personalization data, and a scoring field.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Lead(BaseModel):
    """MongoDB lead document."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    campaign_id: str
    user_id: str
    name: str
    email: str
    lead_hash: str = ""
    company: str = ""
    website: str = ""
    role: str = ""
    linkedin: str = ""
    status: str = "new"
    score: float = 0.0
    lead_quality_score: float = 0.0
    discovery_source: str = "manual"
    research_data: dict[str, Any] = Field(default_factory=dict)
    personalization_data: dict[str, Any] = Field(default_factory=dict)
    enrichment_data: dict[str, Any] = Field(default_factory=dict)
    custom_fields: dict[str, Any] = Field(default_factory=dict)

    # ── Outreach Tracking Fields ───────────────────────────────────────────
    # Team assignment & investor metadata
    focus: str = ""             # Investor's focus area (e.g. "SaaS", "DeepTech")
    assigned_user: str = ""     # display_name of the team member who owns this lead
    notes: str = ""             # Free-text notes visible in the tracker

    # 13 outreach milestone checkboxes (replaces Google Sheet manual tracking)
    linkedin_followed: bool = False
    linkedin_connection_sent: bool = False
    linkedin_connection_accepted: bool = False
    linkedin_first_message_sent: bool = False
    linkedin_reply_received: bool = False
    email_sent: bool = False
    email_opened: bool = False
    email_replied: bool = False
    followup_1_sent: bool = False
    followup_2_sent: bool = False
    followup_3_sent: bool = False
    meeting_scheduled: bool = False
    opportunity_closed: bool = False

    # ── Decoupled Channel Funnel Stages (State Machine) ───────────────────
    linkedin_stage: str = "qualified"  # qualified | pending | connected | failed | completed
    email_stage: str = "qualified"     # drafted | sent | opened | replied | bounced | completed
    campaign_stage: str = "none"       # none | active | replied | meeting_scheduled | converted | opted_out

    # ── Pacing & Cooldown Tracker ──────────────────────────────────────────
    backoff_hours: int = 24
    next_check_pending_at: datetime | None = None
    linkedin_connected_at: datetime | None = None

    # Activity tracking
    last_activity_at: datetime | None = None
    next_followup_at: datetime | None = None

    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    def to_dict(self) -> dict[str, Any]:
        data = self.model_dump()
        data["_id"] = data["id"]
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Lead":
        doc = dict(data)
        if "_id" in doc:
            doc["id"] = doc.pop("_id")
        return cls(**doc)