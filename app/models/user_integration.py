"""
UserIntegration document model for MongoDB.

Stores per-user, per-provider encrypted credentials (API keys, OAuth tokens,
session cookies, etc.).  All sensitive values in ``encrypted_data`` are
encrypted with :mod:`app.utils.security` before storage and decrypted on read.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UserIntegration(BaseModel):
    """MongoDB user_integrations document."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str                       # References users.id
    provider: str                      # groq | tavily | firecrawl | apollo | hunter | linkedin_session | google_sheets
    encrypted_data: dict[str, Any] = Field(default_factory=dict)
    # ^ stores encrypted strings, e.g. {"api_key": "<fernet_token>"}

    is_active: bool = True
    last_tested_at: datetime | None = None
    last_test_ok: bool | None = None   # True = last test passed, False = failed, None = never tested
    last_error: str = ""               # Human-readable last error message (never contains the secret)

    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    def to_dict(self) -> dict[str, Any]:
        data = self.model_dump()
        data["_id"] = data.pop("id")
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UserIntegration":
        doc = dict(data)
        if "_id" in doc:
            doc["id"] = doc.pop("_id")
        return cls(**doc)


PROVIDER_LABELS: dict[str, str] = {
    "groq": "Groq AI",
    "nvidia": "Nvidia NIM",
    "xiaomi": "Xiaomi",
    "gemini": "Google Gemini",
    "tavily": "Tavily Search",
    "firecrawl": "Firecrawl",
    "apollo": "Apollo.io",
    "hunter": "Hunter.io",
    "linkedin_session": "LinkedIn",
    "google_sheets": "Google Sheets",
    "gmail_oauth": "Gmail",
}

# Fields expected for each provider (used for validation and UI hints)
PROVIDER_FIELDS: dict[str, list[str]] = {
    "groq": ["api_key"],
    "nvidia": ["api_key"],
    "xiaomi": ["api_key"],
    "gemini": ["api_key"],
    "tavily": ["api_key"],
    "firecrawl": ["api_key"],
    "apollo": ["api_key"],
    "hunter": ["api_key"],
    "linkedin_session": ["cookie"],    # Playwright cookie JSON
    "google_sheets": ["spreadsheet_id", "service_account_json"],
    "gmail_oauth": [],                 # Managed via OAuth flow, not manual entry
}
