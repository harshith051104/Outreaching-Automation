"""
Reply document model for MongoDB.

Stores an inbound reply to a campaign email together with AI-generated
classification, sentiment analysis, and lead-score adjustment.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Reply(BaseModel):
    """MongoDB reply document."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    email_id: str
    campaign_id: str
    lead_id: str
    user_id: str
    gmail_message_id: str
    gmail_thread_id: str = ""  # Stored to reply in same conversation thread
    body_text: str
    body_html: str = ""
    classification: str = ""   # interested | meeting_requested | not_interested | follow_up_later | spam
    sentiment: str = ""        # positive | neutral | negative
    confidence_score: float = 0.0
    lead_score_delta: float = 0.0
    received_at: datetime = Field(default_factory=_utcnow)
    classified_at: Optional[datetime] = None

    # ── Serialisation helpers ─────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        data = self.model_dump()
        data["_id"] = data.pop("id")
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Reply":
        doc = dict(data)
        if "_id" in doc:
            doc["id"] = doc.pop("_id")
        return cls(**doc)
