"""
Notification document model for MongoDB.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Notification(BaseModel):
    """MongoDB notification document."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str  # Recipient
    sender_id: Optional[str] = None  # Who triggered the action
    type: str  # task_assigned, task_completed, comment_added, suggestion_submitted, suggestion_status_changed
    title: str
    message: str
    reference_id: str  # task or suggestion ID
    reference_type: str  # task, suggestion
    is_read: bool = False
    created_at: datetime = Field(default_factory=_utcnow)

    def to_dict(self) -> dict[str, Any]:
        """Convert to a MongoDB-ready dict, mapping ``id`` → ``_id``."""
        data = self.model_dump()
        data["_id"] = data.pop("id")
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Notification":
        """Construct a ``Notification`` from a MongoDB document dict."""
        doc = dict(data)
        if "_id" in doc:
            doc["id"] = doc.pop("_id")
        return cls(**doc)
