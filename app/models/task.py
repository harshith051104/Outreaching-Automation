"""
Task document model for MongoDB.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Task(BaseModel):
    """MongoDB task document."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str  # Creator
    title: str
    description: str = ""
    status: str = "todo"  # todo, in_progress, review, completed, blocked
    priority: str = "medium"  # low, medium, high, critical
    due_date: Optional[datetime] = None
    assigned_to: Optional[str] = None  # User ID
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    def to_dict(self) -> dict[str, Any]:
        """Convert to a MongoDB-ready dict, mapping ``id`` → ``_id``."""
        data = self.model_dump()
        data["_id"] = data.pop("id")
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Task":
        """Construct a ``Task`` from a MongoDB document dict."""
        doc = dict(data)
        if "_id" in doc:
            doc["id"] = doc.pop("_id")
        return cls(**doc)
