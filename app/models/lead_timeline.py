"""
LeadTimeline document model for MongoDB.

Records every outreach action, status change, and note for a lead.
The timeline is the audit trail that replaces manual Google Sheet logging.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# All valid event type identifiers
EVENT_TYPES = {
    "followed",
    "connection_sent",
    "connection_accepted",
    "first_message_sent",
    "linkedin_reply",
    "email_sent",
    "email_opened",
    "email_replied",
    "followup_1_sent",
    "followup_2_sent",
    "followup_3_sent",
    "meeting_scheduled",
    "opportunity_closed",
    "status_changed",
    "note_added",
    "checkbox_updated",
    "sheet_synced",
    "assigned",
}

# Human-readable labels for timeline events
EVENT_LABELS: dict[str, str] = {
    "followed": "Followed on LinkedIn",
    "connection_sent": "LinkedIn connection request sent",
    "connection_accepted": "LinkedIn connection accepted 🎉",
    "first_message_sent": "First LinkedIn message sent",
    "linkedin_reply": "Replied on LinkedIn 💬",
    "email_sent": "Email sent",
    "email_opened": "Email opened 👁",
    "email_replied": "Replied to email 💬",
    "followup_1_sent": "Follow-up #1 sent",
    "followup_2_sent": "Follow-up #2 sent",
    "followup_3_sent": "Follow-up #3 sent",
    "meeting_scheduled": "Meeting scheduled 📅",
    "opportunity_closed": "Opportunity closed ✅",
    "status_changed": "Status changed",
    "note_added": "Note added",
    "checkbox_updated": "Tracker updated",
    "sheet_synced": "Google Sheet synced",
    "assigned": "Assigned to team member",
}


class LeadTimeline(BaseModel):
    """MongoDB lead_timeline document."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    lead_id: str                  # References leads.id
    user_id: str                  # The user who performed this action
    campaign_id: str = ""
    event_type: str               # One of EVENT_TYPES
    description: str = ""         # Human-readable summary (auto-generated or manual)
    metadata: dict[str, Any] = Field(default_factory=dict)
    # ^ Extra context, e.g. {"field": "email_sent", "old_value": false, "new_value": true}

    created_at: datetime = Field(default_factory=_utcnow)

    def to_dict(self) -> dict[str, Any]:
        data = self.model_dump()
        # Keep 'id' in doc for API responses; add '_id' for MongoDB uniqueness
        data["_id"] = data["id"]
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LeadTimeline":
        doc = dict(data)
        if "_id" in doc:
            doc["id"] = doc.pop("_id")
        return cls(**doc)
