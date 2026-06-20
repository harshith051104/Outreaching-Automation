"""
User document model for MongoDB.

Represents a registered platform user with hashed credentials.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(BaseModel):
    """MongoDB user document."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    email: str
    name: str
    hashed_password: str
    is_active: bool = True
    # Role-Based Access Control: member | manager | admin
    role: str = "member"
    # display_name is matched against Google Sheets tab names for sync
    display_name: str = ""
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    # ── Serialisation helpers ─────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """Convert to a MongoDB-ready dict, mapping ``id`` → ``_id``."""
        data = self.model_dump()
        data["_id"] = data.pop("id")
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "User":
        """Construct a ``User`` from a MongoDB document dict."""
        doc = dict(data)  # shallow copy to avoid mutating the original
        if "_id" in doc:
            doc["id"] = doc.pop("_id")
        return cls(**doc)
