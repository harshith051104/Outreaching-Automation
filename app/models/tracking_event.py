"""
TrackingEvent document model for MongoDB.

Each tracking event records a single open, click, reply, or bounce for
a specific email, linking back to the campaign and lead.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TrackingEvent(BaseModel):
    """MongoDB tracking-event document."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    tracking_id: str
    email_id: str
    campaign_id: str
    lead_id: str
    event_type: str  # open | click | reply | bounce
    ip_address: str = ""
    user_agent: str = ""
    url: str = ""  # populated for click events
    timestamp: datetime = Field(default_factory=_utcnow)

    # ── Serialisation helpers ─────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        data = self.model_dump()
        data["_id"] = data.pop("id")
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TrackingEvent":
        doc = dict(data)
        if "_id" in doc:
            doc["id"] = doc.pop("_id")
        return cls(**doc)
