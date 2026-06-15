"""
Suggestion document model for MongoDB.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Suggestion(BaseModel):
    """MongoDB suggestion document."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: Optional[str] = None  # None if anonymous
    title: str
    description: str
    category: str  # suggestion, feature_request, improvement, feedback
    anonymous: bool = False
    status: str = "pending"  # pending, under_review, accepted, rejected, implemented
    votes: List[str] = Field(default_factory=list)  # List of user_ids
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    # Global feedback widget metadata
    submitted_from: str = "page"  # page, widget
    page_name: Optional[str] = None
    page_url: Optional[str] = None
    screenshot_url: Optional[str] = None
    has_screenshot: bool = False
    browser_info: Optional[str] = None

    # AI analysis metadata
    ai_summary: Optional[str] = None
    ai_priority: Optional[str] = None
    ai_business_impact: Optional[str] = None
    ai_suggested_category: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to a MongoDB-ready dict, mapping ``id`` → ``_id``."""
        data = self.model_dump()
        data["_id"] = data.pop("id")
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Suggestion":
        """Construct a ``Suggestion`` from a MongoDB document dict."""
        doc = dict(data)
        if "_id" in doc:
            doc["id"] = doc.pop("_id")
        return cls(**doc)
