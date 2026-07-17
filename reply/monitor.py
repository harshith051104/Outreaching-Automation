"""
Reply monitor — detects new Gmail replies and prevents duplicate processing.

Deterministic — no AI calls. Reads Gmail via existing gmail_service.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from app.config.mongodb_config import get_database

logger = logging.getLogger(__name__)


async def get_unprocessed_replies(campaign_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Find reply documents that haven't been analyzed yet.

    A reply is unprocessed if it has no 'intent' field in the analysis.
    """
    db = await get_database()
    query: Dict[str, Any] = {"analysis": None}
    if campaign_id:
        query["campaign_id"] = campaign_id

    cursor = db.replies.find(query, {"_id": 0}).sort("received_at", -1).limit(100)
    return await cursor.to_list(length=100)


async def is_duplicate_reply(gmail_message_id: str) -> bool:
    """Check if a reply has already been processed."""
    if not gmail_message_id:
        return False
    db = await get_database()
    existing = await db.replies.find_one(
        {"gmail_message_id": gmail_message_id},
        {"_id": 1},
    )
    return existing is not None


async def get_processed_message_ids() -> Set[str]:
    """Get all already-processed Gmail message IDs for dedup."""
    db = await get_database()
    cursor = db.replies.find(
        {"gmail_message_id": {"$ne": ""}},
        {"gmail_message_id": 1, "_id": 0},
    )
    docs = await cursor.to_list(length=10000)
    return {d["gmail_message_id"] for d in docs if d.get("gmail_message_id")}


async def get_reply_email_context(tracking_id: str) -> Optional[Dict[str, Any]]:
    """
    Resolve a tracking_id to the original email + lead context.

    Returns dict with email_doc, lead_doc, campaign_doc.
    """
    db = await get_database()
    email_doc = await db.emails.find_one({"tracking_id": tracking_id})
    if not email_doc:
        return None

    lead_doc = None
    if email_doc.get("lead_id"):
        lead_doc = await db.leads.find_one({"id": email_doc["lead_id"]})

    campaign_doc = None
    if email_doc.get("campaign_id"):
        campaign_doc = await db.campaigns.find_one({"id": email_doc["campaign_id"]})

    return {
        "email_doc": email_doc,
        "lead_doc": lead_doc,
        "campaign_doc": campaign_doc,
    }
