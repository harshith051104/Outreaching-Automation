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