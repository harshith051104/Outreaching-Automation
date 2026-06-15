"""
Analytics document model for MongoDB.

Stores campaign-level aggregated metrics that are updated asynchronously
by the analytics background task whenever new events arrive.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Analytics(BaseModel):
    """MongoDB analytics (campaign-level aggregate) document."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    campaign_id: str
    user_id: str

    # ── Absolute counters ─────────────────────────────────────────────────
    total_sent: int = 0
    total_delivered: int = 0
    total_opens: int = 0
    unique_opens: int = 0
    total_clicks: int = 0
    unique_clicks: int = 0
    total_replies: int = 0
    positive_replies: int = 0
    bounces: int = 0

    # ── Derived rates (0.0 – 1.0) ────────────────────────────────────────
    open_rate: float = 0.0
    click_rate: float = 0.0
    reply_rate: float = 0.0
    bounce_rate: float = 0.0

    # ── Time-series data ──────────────────────────────────────────────────
    # Each entry: {"date": "2025-01-15", "sent": 10, "opens": 3, "clicks": 1, "replies": 0}
    daily_stats: list[dict[str, Any]] = Field(default_factory=list)

    updated_at: datetime = Field(default_factory=_utcnow)

    # ── Serialisation helpers ─────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        data = self.model_dump()
        data["_id"] = data.pop("id")
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Analytics":
        doc = dict(data)
        if "_id" in doc:
            doc["id"] = doc.pop("_id")
        return cls(**doc)

    def recalculate_rates(self) -> None:
        """Recompute derived rate fields from absolute counters."""
        if self.total_sent > 0:
            self.open_rate = round(self.unique_opens / self.total_sent, 4)
            self.click_rate = round(self.unique_clicks / self.total_sent, 4)
            self.reply_rate = round(self.total_replies / self.total_sent, 4)
            self.bounce_rate = round(self.bounces / self.total_sent, 4)
        else:
            self.open_rate = 0.0
            self.click_rate = 0.0
            self.reply_rate = 0.0
            self.bounce_rate = 0.0
