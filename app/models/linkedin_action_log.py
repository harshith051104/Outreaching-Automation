"""
LinkedInActionLog model for MongoDB.

Logs all successfully executed LinkedIn actions (connect request, message, etc.)
per user/campaign to enforce dynamic daily rate limits.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4
from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class LinkedInActionLog(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    lead_id: str
    campaign_id: str
    action_type: str  # connect | follow_up | message
    created_at: datetime = Field(default_factory=_utcnow)

    def to_dict(self) -> dict:
        data = self.model_dump()
        data["_id"] = data.pop("id")
        return data

    @classmethod
    def from_dict(cls, data: dict) -> LinkedInActionLog:
        doc = dict(data)
        if "_id" in doc:
            doc["id"] = doc.pop("_id")
        return cls(**doc)
