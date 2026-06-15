"""
Campaign document model for MongoDB.

A campaign groups a set of leads, an email template, and sending settings
together so the platform can execute automated outreach.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _default_settings() -> dict[str, Any]:
    """Return the default campaign settings dict."""
    return {
        "max_emails_per_day": 50,
        "delay_between_emails_seconds": 60,
        "follow_up_count": 3,
        "follow_up_delay_hours": 48,
        "tone": "professional",
        "timezone": "UTC",
    }


class Campaign(BaseModel):
    """MongoDB campaign document."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    name: str
    description: str = ""
    status: str = "draft"
    subject_template: str = ""
    body_template: str = ""
    gmail_account_id: str = ""
    settings: dict[str, Any] = Field(default_factory=_default_settings)
    sequence_steps: list[dict[str, Any]] = Field(default_factory=list)
    total_leads: int = 0
    sent_count: int = 0
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    # ── Serialisation helpers ─────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        data = self.model_dump()
        data["_id"] = data.pop("id")
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Campaign":
        doc = dict(data)
        if "_id" in doc:
            doc["id"] = doc.pop("_id")
        return cls(**doc)
