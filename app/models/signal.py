"""
Signal document model for MongoDB.

Stores signal intelligence events scraped by the Signal Intelligence Agent,
categorized into hiring, funding, tech stack changes, expansion, and pricing tweaks.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List, Dict
from uuid import uuid4

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Signal(BaseModel):
    """MongoDB signal document for scraping and personalization hooks."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    lead_id: str = ""
    company_name: str
    signal_type: str = ""
    description: str = ""
    url_source: str = ""
    
    signal: str = ""
    category: str = ""
    score: float = 0.0
    hook: str = ""
    
    published_at: datetime = Field(default_factory=_utcnow)
    signal_freshness_score: float = 100.0
    
    growth_indicators: List[str] = Field(default_factory=list)
    personalization_angles: List[str] = Field(default_factory=list)
    recommended_hooks: List[str] = Field(default_factory=list)
    
    created_at: datetime = Field(default_factory=_utcnow)

    def update_freshness(self) -> None:
        """Decay freshness score exponentially based on days elapsed since publication."""
        import math
        now = datetime.now(timezone.utc)
        diff = now - self.published_at
        days_elapsed = max(0.0, diff.total_seconds() / 86400.0)
        self.signal_freshness_score = round(100.0 * math.exp(-0.02 * days_elapsed), 2)

    def to_dict(self) -> Dict[str, Any]:
        self.update_freshness()
        data = self.model_dump()
        data["_id"] = data.pop("id")
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Signal":
        doc = dict(data)
        if "_id" in doc:
            doc["id"] = doc.pop("_id")
        return cls(**doc)