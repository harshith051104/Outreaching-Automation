"""
GmailAccount document model for MongoDB.

Stores OAuth2 credentials for a connected Gmail account so the platform
can send emails on behalf of the user.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from app.config.gmail_config import GMAIL_SCOPES


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class GmailAccount(BaseModel):
    """Stored Gmail OAuth2 connection."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    email: str
    access_token: str
    refresh_token: str
    token_uri: str = "https://oauth2.googleapis.com/token"
    client_id: str = ""
    client_secret: str = ""
    scopes: list[str] = Field(default_factory=lambda: list(GMAIL_SCOPES))
    connected_at: datetime = Field(default_factory=_utcnow)
    is_active: bool = True
    name: str = ""

    # ── Serialisation helpers ─────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        data = self.model_dump()
        data["_id"] = data.pop("id")
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GmailAccount":
        doc = dict(data)
        if "_id" in doc:
            doc["id"] = doc.pop("_id")
        return cls(**doc)

    def to_credentials_dict(self) -> dict[str, Any]:
        """Return the subset of fields needed by ``gmail_config`` helpers."""
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "token_uri": self.token_uri,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scopes": self.scopes,
        }
