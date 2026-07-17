"""
Lead status manager — updates lead status in MongoDB based on intent.

Deterministic — no AI calls.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from app.config.mongodb_config import get_database
from reply.models import LeadStatus


async def update_lead_status(
    lead_id: str,
    new_status: LeadStatus,
    engagement_delta: float = 0.0,
) -> bool:
    """
    Update a lead's status and optionally adjust engagement score.

    Returns True if the lead was found and updated.
    """
    if not lead_id:
        return False

    db = await get_database()
    now = datetime.now(timezone.utc)

    update: dict = {
        "status": new_status.value,
        "updated_at": now,
    }

    if engagement_delta != 0.0:
        update["$inc"] = {"engagement_score": engagement_delta}

    if update.get("$inc"):
        result = await db.leads.update_one(
            {"id": lead_id},
            {"$set": {"status": new_status.value, "updated_at": now},
             "$inc": {"engagement_score": engagement_delta}},
        )
    else:
        result = await db.leads.update_one(
            {"id": lead_id},
            {"$set": update},
        )

    return result.modified_count > 0


async def get_lead_status(lead_id: str) -> Optional[str]:
    """Get current lead status."""
    if not lead_id:
        return None
    db = await get_database()
    lead = await db.leads.find_one({"id": lead_id}, {"status": 1, "_id": 0})
    return lead.get("status") if lead else None
