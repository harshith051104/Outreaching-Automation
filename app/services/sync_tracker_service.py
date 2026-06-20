"""
Sync Tracker Service — Scoped Google Sheets Synchronization

Integrates local MongoDB outreach changes with gspread sheets.
Wraps the lower-level sheets_sync_service operations with strict multi-tenant validation.
"""

from __future__ import annotations

import logging
from typing import Any

from app.config.mongodb_config import get_database
from app.services.sheets_sync_service import (
    push_lead_to_sheet,
    pull_sheet_updates,
    push_bulk
)

logger = logging.getLogger(__name__)


async def sync_lead_to_sheet(lead_id: str, user_id: str) -> None:
    """Pushes a single lead's tracker updates to Google Sheets after validation."""
    db = await get_database()
    # Scoped lead verification
    lead = await db.leads.find_one({"id": lead_id, "user_id": user_id})
    if not lead:
        # Check if the lead is assigned to this user instead
        lead = await db.leads.find_one({"id": lead_id, "assigned_user": user_id})
        
    if not lead:
        logger.warning("Lead %s unauthorized or not found for user %s sheets sync.", lead_id, user_id)
        return
        
    await push_lead_to_sheet(lead_id, user_id)


async def sync_sheet_to_mongodb(user_id: str) -> int:
    """Pulls Google Sheets updates and merges them back to MongoDB."""
    logger.info("Starting sheet-to-mongodb sync pull for user: %s", user_id)
    return await pull_sheet_updates(user_id)


async def sync_campaign_to_sheet(campaign_id: str, user_id: str) -> int:
    """Pushes all campaign leads to Google Sheets after strict campaign validation."""
    db = await get_database()
    campaign = await db.campaigns.find_one({"id": campaign_id, "user_id": user_id})
    if not campaign:
        logger.warning("Campaign %s not found or unauthorized for user %s sheets bulk sync.", campaign_id, user_id)
        return 0
        
    return await push_bulk(campaign_id, user_id)
