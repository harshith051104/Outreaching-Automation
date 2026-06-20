"""
Outreach Tracker Service — manages lead tracking checkboxes, timeline events,
and team progress aggregation.

This service replaces manual Google Sheet tracking with structured, auditable
state stored in MongoDB.  Every checkbox change creates a timeline event and
optionally triggers a Google Sheet sync.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.config.mongodb_config import get_database
from app.models.lead_timeline import EVENT_LABELS, LeadTimeline

logger = logging.getLogger(__name__)

# All checkbox field names that can be toggled via the tracker
CHECKBOX_FIELDS = {
    "linkedin_followed",
    "linkedin_connection_sent",
    "linkedin_connection_accepted",
    "linkedin_first_message_sent",
    "linkedin_reply_received",
    "email_sent",
    "email_opened",
    "email_replied",
    "followup_1_sent",
    "followup_2_sent",
    "followup_3_sent",
    "meeting_scheduled",
    "opportunity_closed",
}

# Map checkbox fields → timeline event types
CHECKBOX_TO_EVENT: dict[str, str] = {
    "linkedin_followed": "followed",
    "linkedin_connection_sent": "connection_sent",
    "linkedin_connection_accepted": "connection_accepted",
    "linkedin_first_message_sent": "first_message_sent",
    "linkedin_reply_received": "linkedin_reply",
    "email_sent": "email_sent",
    "email_opened": "email_opened",
    "email_replied": "email_replied",
    "followup_1_sent": "followup_1_sent",
    "followup_2_sent": "followup_2_sent",
    "followup_3_sent": "followup_3_sent",
    "meeting_scheduled": "meeting_scheduled",
    "opportunity_closed": "opportunity_closed",
}


async def update_checkboxes(
    lead_id: str,
    user_id: str,
    updates: dict[str, bool],
    trigger_sync: bool = True,
) -> dict[str, Any]:
    """
    Update one or more tracking checkboxes for a lead.

    Creates a timeline event for each changed field.
    Optionally triggers a Google Sheet sync.

    Returns the updated lead document.
    """
    db = await get_database()

    # Validate all field names
    invalid = set(updates.keys()) - CHECKBOX_FIELDS - {"notes", "next_followup_at", "assigned_user", "focus", "name", "email", "linkedin", "company"}
    if invalid:
        raise ValueError(f"Invalid tracker fields: {invalid}")

    lead = await db.leads.find_one({"id": lead_id})
    if not lead:
        raise ValueError(f"Lead '{lead_id}' not found.")

    now = datetime.now(timezone.utc)
    set_fields: dict[str, Any] = {"updated_at": now, "last_activity_at": now}

    # Process checkbox changes
    for field, new_value in updates.items():
        if field in CHECKBOX_FIELDS:
            old_value = lead.get(field, False)
            set_fields[field] = new_value

            if old_value != new_value:
                event_type = CHECKBOX_TO_EVENT.get(field, "checkbox_updated")
                label = EVENT_LABELS.get(event_type, field.replace("_", " ").title())
                await _create_timeline_event(
                    lead_id=lead_id,
                    user_id=user_id,
                    campaign_id=lead.get("campaign_id", ""),
                    event_type=event_type,
                    description=label,
                    metadata={"field": field, "old_value": old_value, "new_value": new_value},
                )

                # Create notification for important events
                if event_type in ("connection_accepted", "linkedin_reply", "email_replied", "meeting_scheduled"):
                    await _create_notification(
                        user_id=user_id,
                        event_type=event_type,
                        lead_name=lead.get("name", "Unknown"),
                        lead_id=lead_id,
                    )

        elif field == "notes":
            set_fields["notes"] = updates["notes"]
            if updates["notes"]:
                await _create_timeline_event(
                    lead_id=lead_id,
                    user_id=user_id,
                    campaign_id=lead.get("campaign_id", ""),
                    event_type="note_added",
                    description="Note added",
                    metadata={"note": updates["notes"][:200]},
                )
        elif field in ("next_followup_at", "assigned_user", "focus", "name", "email", "linkedin", "company"):
            set_fields[field] = updates[field]

    await db.leads.update_one({"id": lead_id}, {"$set": set_fields})

    if trigger_sync:
        try:
            from app.services.sheets_sync_service import push_lead_to_sheet
            await push_lead_to_sheet(lead_id, user_id)
        except Exception as exc:
            logger.warning("Google Sheet sync skipped for lead %s: %s", lead_id, exc)

    updated = await db.leads.find_one({"id": lead_id})
    if updated:
        updated.pop("_id", None)
    return updated or {}


async def get_timeline(lead_id: str, limit: int = 100) -> list[dict[str, Any]]:
    """Return the activity timeline for a lead, newest first."""
    db = await get_database()
    events = await db.lead_timeline.find(
        {"lead_id": lead_id}
    ).sort("created_at", -1).limit(limit).to_list(length=limit)

    result = []
    for e in events:
        e.pop("_id", None)
        result.append(e)
    return result


async def log_timeline_event(
    lead_id: str,
    user_id: str,
    event_type: str,
    description: str,
    metadata: dict | None = None,
) -> dict[str, Any]:
    """Manually log a timeline event for a lead."""
    db = await get_database()
    lead = await db.leads.find_one({"id": lead_id})
    if not lead:
        raise ValueError(f"Lead '{lead_id}' not found.")

    event = await _create_timeline_event(
        lead_id=lead_id,
        user_id=user_id,
        campaign_id=lead.get("campaign_id", ""),
        event_type=event_type,
        description=description,
        metadata=metadata or {},
    )
    return event


async def get_team_progress(campaign_id: str | None = None) -> list[dict[str, Any]]:
    """
    Aggregate tracker stats per assigned_user across all (or one) campaign.

    Returns a list of dicts with per-user completion rates for each checkbox.
    """
    db = await get_database()

    match_filter: dict = {}
    if campaign_id:
        match_filter["campaign_id"] = campaign_id

    pipeline = [
        {"$match": match_filter},
        {"$group": {
            "_id": "$assigned_user",
            "total": {"$sum": 1},
            "linkedin_connection_sent": {"$sum": {"$cond": ["$linkedin_connection_sent", 1, 0]}},
            "linkedin_connection_accepted": {"$sum": {"$cond": ["$linkedin_connection_accepted", 1, 0]}},
            "linkedin_first_message_sent": {"$sum": {"$cond": ["$linkedin_first_message_sent", 1, 0]}},
            "linkedin_reply_received": {"$sum": {"$cond": ["$linkedin_reply_received", 1, 0]}},
            "email_sent": {"$sum": {"$cond": ["$email_sent", 1, 0]}},
            "email_opened": {"$sum": {"$cond": ["$email_opened", 1, 0]}},
            "email_replied": {"$sum": {"$cond": ["$email_replied", 1, 0]}},
            "followup_1_sent": {"$sum": {"$cond": ["$followup_1_sent", 1, 0]}},
            "followup_2_sent": {"$sum": {"$cond": ["$followup_2_sent", 1, 0]}},
            "followup_3_sent": {"$sum": {"$cond": ["$followup_3_sent", 1, 0]}},
            "meeting_scheduled": {"$sum": {"$cond": ["$meeting_scheduled", 1, 0]}},
            "opportunity_closed": {"$sum": {"$cond": ["$opportunity_closed", 1, 0]}},
        }},
        {"$sort": {"_id": 1}},
    ]

    results = await db.leads.aggregate(pipeline).to_list(length=50)
    members = []
    for r in results:
        total = r["total"] or 1
        completed = r.get("opportunity_closed", 0)
        in_progress = r.get("email_sent", 0) + r.get("linkedin_first_message_sent", 0)
        members.append({
            "user_id": r["_id"] or "",
            "display_name": r["_id"] or "Unassigned",
            "total_leads": r["total"],
            "completed": completed,
            "in_progress": in_progress,
            "meeting_scheduled": r.get("meeting_scheduled", 0),
            "opportunity_closed": r.get("opportunity_closed", 0),
            "completion_rate": round((completed / total) * 100, 1),
            # Individual milestones (for detailed views)
            "linkedin_connection_sent": r.get("linkedin_connection_sent", 0),
            "linkedin_connection_accepted": r.get("linkedin_connection_accepted", 0),
            "linkedin_first_message_sent": r.get("linkedin_first_message_sent", 0),
            "linkedin_reply_received": r.get("linkedin_reply_received", 0),
            "email_sent": r.get("email_sent", 0),
            "email_opened": r.get("email_opened", 0),
            "email_replied": r.get("email_replied", 0),
            "followup_1_sent": r.get("followup_1_sent", 0),
            "followup_2_sent": r.get("followup_2_sent", 0),
            "followup_3_sent": r.get("followup_3_sent", 0),
        })

    total_leads = sum(m["total_leads"] for m in members)
    total_completed = sum(m["completed"] for m in members)
    return {
        "total_members": len(members),
        "total_leads": total_leads,
        "total_completed": total_completed,
        "members": members,
    }



# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────


async def _create_timeline_event(
    lead_id: str,
    user_id: str,
    campaign_id: str,
    event_type: str,
    description: str,
    metadata: dict,
) -> dict[str, Any]:
    db = await get_database()
    event = LeadTimeline(
        lead_id=lead_id,
        user_id=user_id,
        campaign_id=campaign_id,
        event_type=event_type,
        description=description,
        metadata=metadata,
    )
    doc = event.to_dict()
    await db.lead_timeline.insert_one(doc)
    doc.pop("_id", None)
    return doc


async def _create_notification(
    user_id: str,
    event_type: str,
    lead_name: str,
    lead_id: str,
) -> None:
    """Create a notification for important outreach events."""
    db = await get_database()
    type_to_message = {
        "connection_accepted": f"LinkedIn connection accepted by {lead_name}",
        "linkedin_reply": f"LinkedIn reply received from {lead_name}",
        "email_replied": f"Email reply from {lead_name}",
        "meeting_scheduled": f"Meeting scheduled with {lead_name} 📅",
    }
    message = type_to_message.get(event_type, f"Activity on {lead_name}")
    now = datetime.now(timezone.utc)

    await db.notifications.insert_one({
        "id": LeadTimeline(lead_id=lead_id, user_id=user_id, campaign_id="", event_type=event_type).id,
        "user_id": user_id,
        "type": event_type,
        "message": message,
        "data": {"lead_id": lead_id, "lead_name": lead_name},
        "read": False,
        "created_at": now,
    })
