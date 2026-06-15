"""
ActivityLog document model for MongoDB.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ActivityLog(BaseModel):
    """MongoDB activity log document."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    user_name: str
    action: str  # task_created, task_updated, status_changed, comment_added, suggestion_submitted
    reference_id: str
    reference_type: str  # task, suggestion
    details: str
    created_at: datetime = Field(default_factory=_utcnow)

    def to_dict(self) -> dict[str, Any]:
        """Convert to a MongoDB-ready dict, mapping ``id`` → ``_id``."""
        data = self.model_dump()
        data["_id"] = data.pop("id")
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ActivityLog":
        """Construct an ``ActivityLog`` from a MongoDB document dict."""
        doc = dict(data)
        if "_id" in doc:
            doc["id"] = doc.pop("_id")
        return cls(**doc)
