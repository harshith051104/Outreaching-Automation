"""
Email document model for MongoDB.

Represents a single outbound email – either pending or already sent – with
tracking metadata and Gmail thread/message IDs.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Email(BaseModel):
    """MongoDB email document."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    campaign_id: str
    lead_id: str
    user_id: str
    gmail_account_id: str
    subject: str
    body_html: str
    body_text: str = ""
    tracking_id: str = Field(default_factory=lambda: str(uuid4()))
    gmail_message_id: str = ""
    gmail_thread_id: str = ""
    status: str = "pending"
    sequence_number: int = 1
    sent_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=_utcnow)

    # ── Serialisation helpers ─────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        data = self.model_dump()
        data["_id"] = data.pop("id")
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Email":
        doc = dict(data)
        if "_id" in doc:
            doc["id"] = doc.pop("_id")
        return cls(**doc)
