"""
FlowExecutionLog document model for MongoDB.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class FlowExecutionLog(BaseModel):
    """MongoDB flow execution log document."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    flow_run_id: str
    node_id: str
    node_type: str
    status: str  # running, completed, failed, waiting_for_approval, waiting_for_delay
    started_at: datetime = Field(default_factory=_utcnow)
    completed_at: Optional[datetime] = None
    message: str
    created_at: datetime = Field(default_factory=_utcnow)

    def to_dict(self) -> dict[str, Any]:
        """Convert to a MongoDB-ready dict, mapping ``id`` → ``_id``."""
        data = self.model_dump()
        data["_id"] = data.pop("id")
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FlowExecutionLog":
        """Construct a ``FlowExecutionLog`` from a MongoDB document dict."""
        doc = dict(data)
        if "_id" in doc:
            doc["id"] = doc.pop("_id")
        return cls(**doc)
