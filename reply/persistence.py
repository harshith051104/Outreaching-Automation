"""
MongoDB persistence for reply analysis results.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.config.mongodb_config import get_database
from app.utils.id_generator import generate_id

from reply.models import ReplyRecord, AnalysisResult, WorkflowEvent


async def save_reply(record: ReplyRecord) -> ReplyRecord:
    """Insert a reply record."""
    db = await get_database()
    if not record.id:
        record.id = generate_id()
    record.created_at = datetime.now(timezone.utc)
    await db.replies.insert_one(record.to_doc())
    return record


async def save_analysis(
    reply_id: str,
    analysis: AnalysisResult,
) -> bool:
    """Update a reply document with analysis results."""
    db = await get_database()
    result = await db.replies.update_one(
        {"id": reply_id},
        {"$set": {"analysis": analysis.to_doc(), "analyzed_at": datetime.now(timezone.utc)}},
    )
    return result.modified_count > 0


async def get_reply(reply_id: str) -> Optional[Dict[str, Any]]:
    """Fetch a reply by ID."""
    db = await get_database()
    doc = await db.replies.find_one({"id": reply_id}, {"_id": 0})
    return doc


async def get_replies_by_lead(lead_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Fetch all replies for a lead."""
    db = await get_database()
    cursor = (
        db.replies.find({"lead_id": lead_id}, {"_id": 0})
        .sort("received_at", -1)
        .limit(limit)
    )
    return await cursor.to_list(length=limit)


async def get_replies_by_campaign(campaign_id: str, limit: int = 200) -> List[Dict[str, Any]]:
    """Fetch all replies for a campaign."""
    db = await get_database()
    cursor = (
        db.replies.find({"campaign_id": campaign_id}, {"_id": 0})
        .sort("received_at", -1)
        .limit(limit)
    )
    return await cursor.to_list(length=limit)


async def save_workflow_event(event: WorkflowEvent) -> None:
    """Persist a workflow event for audit trail."""
    db = await get_database()
    doc = event.to_doc()
    doc["id"] = generate_id()
    await db.workflow_events.insert_one(doc)
