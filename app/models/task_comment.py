"""
TaskComment document model for MongoDB.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TaskComment(BaseModel):
    """MongoDB task comment document."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    task_id: str
    user_id: str  # Author
    message: str
    created_at: datetime = Field(default_factory=_utcnow)

    def to_dict(self) -> dict[str, Any]:
        """Convert to a MongoDB-ready dict, mapping ``id`` → ``_id``."""
        data = self.model_dump()
        data["_id"] = data.pop("id")
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskComment":
        """Construct a ``TaskComment`` from a MongoDB document dict."""
        doc = dict(data)
        if "_id" in doc:
            doc["id"] = doc.pop("_id")
        return cls(**doc)
