"""
Content document model for MongoDB.

Stores the generated 30-day LinkedIn Content Calendar, content pillars,
themes, and generated copy for outreach campaigns.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List, Dict
from uuid import uuid4

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Content(BaseModel):
    """MongoDB content document for social media planning."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    campaign_id: str = ""
    target_audience: str = ""
    themes: List[str] = Field(default_factory=list)
    posting_frequency: str = "daily"
    content_pillars: List[str] = Field(default_factory=list)
    recommended_ctas: List[str] = Field(default_factory=list)
    
    # List of generated posts, e.g. [{"day": 1, "type": "founder post", "text": "...", "scheduled_time": "..."}]
    calendar: List[Dict[str, Any]] = Field(default_factory=list)
    
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    def to_dict(self) -> Dict[str, Any]:
        data = self.model_dump()
        data["_id"] = data.pop("id")
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Content":
        doc = dict(data)
        if "_id" in doc:
            doc["id"] = doc.pop("_id")
        return cls(**doc)
