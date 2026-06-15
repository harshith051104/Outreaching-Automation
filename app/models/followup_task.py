"""
FollowupTask document model for MongoDB.

Represents a scheduled follow-up email in a sequence. The background
scheduler picks these up and dispatches them at ``scheduled_at``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class FollowupTask(BaseModel):
    """MongoDB follow-up task document."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    email_id: str
    campaign_id: str
    lead_id: str
    user_id: str
    sequence_number: int
    subject: str = ""
    body_html: str = ""
    scheduled_at: datetime
    status: str = "pending"  # pending | sent | cancelled | failed
    sent_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=_utcnow)

    # ── Serialisation helpers ─────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        data = self.model_dump()
        data["_id"] = data.pop("id")
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FollowupTask":
        doc = dict(data)
        if "_id" in doc:
            doc["id"] = doc.pop("_id")
        return cls(**doc)
