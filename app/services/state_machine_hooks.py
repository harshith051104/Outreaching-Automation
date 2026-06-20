"""
State Machine Hooks — Handles decoupled stage transitions for LinkedIn, Email, and Campaign channels.

Enforces:
- Automatic synchronization with tracking checkboxes.
- Creation of audit timeline events.
- Transition effects (like exponential backoff calculations for LinkedIn acceptance checks).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any

from app.config.mongodb_config import get_database
from app.services.outreach_tracker_service import update_checkboxes

logger = logging.getLogger(__name__)


async def on_lead_stage_entered(
    lead_id: str,
    user_id: str,
    channel: str,
    new_state: str,
    trigger_sync: bool = True,
) -> None:
    """
    Hook triggered when a lead enters a new stage in a specific channel.
    Synchronizes the local lead document, schedules updates, logs timeline events,
    and updates Google Sheets.
    """
    db = await get_database()
    lead = await db.leads.find_one({"id": lead_id})
    if not lead:
        logger.warning("Lead %s not found for stage hook.", lead_id)
        return

    now = datetime.now(timezone.utc)
    updates: dict[str, Any] = {"updated_at": now}

    # 1. Update the appropriate stage field
    if channel == "linkedin":
        updates["linkedin_stage"] = new_state
        if new_state == "pending":
            # Set default 24h backoff for acceptance checks
            updates["backoff_hours"] = 24
            updates["next_check_pending_at"] = now + timedelta(hours=24)
    elif channel == "email":
        updates["email_stage"] = new_state
    elif channel == "campaign":
        updates["campaign_stage"] = new_state

    # Commit structural stage fields first
    await db.leads.update_one({"id": lead_id}, {"$set": updates})

    # 2. Synchronize stage with tracker checkboxes
    checkbox_updates: dict[str, bool] = {}

    if channel == "linkedin":
        if new_state == "pending":
            checkbox_updates["linkedin_connection_sent"] = True
        elif new_state == "connected":
            checkbox_updates["linkedin_connection_accepted"] = True
        elif new_state == "completed":
            checkbox_updates["linkedin_reply_received"] = True

    elif channel == "email":
        if new_state == "sent":
            checkbox_updates["email_sent"] = True
        elif new_state == "opened":
            checkbox_updates["email_opened"] = True
        elif new_state == "replied":
            checkbox_updates["email_replied"] = True

    elif channel == "campaign":
        if new_state == "meeting_scheduled":
            checkbox_updates["meeting_scheduled"] = True
        elif new_state == "converted":
            checkbox_updates["opportunity_closed"] = True

    # 3. Apply changes via outreach_tracker_service (triggers timeline & sheet sync)
    if checkbox_updates:
        try:
            await update_checkboxes(
                lead_id=lead_id,
                user_id=user_id,
                updates=checkbox_updates,
                trigger_sync=trigger_sync,
            )
            logger.info("Successfully updated tracking checkboxes for lead %s state: %s", lead_id, new_state)
        except Exception as exc:
            logger.error("Failed to update tracking checkboxes for lead %s: %s", lead_id, exc)
