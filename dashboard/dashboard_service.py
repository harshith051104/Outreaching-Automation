"""
Dashboard Service — aggregates data from backend modules.

Read-only. Never executes business logic.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from dashboard.models import (
    DashboardSummary, CampaignSummary, ComponentHealth,
    SystemHealth, HealthStatus, ExecutionLog,
)

logger = logging.getLogger(__name__)


async def _get_db():
    from app.config.mongodb_config import get_database
    return await get_database()


async def get_dashboard_summary(user_id: str = "") -> DashboardSummary:
    """Aggregate top-level dashboard stats from MongoDB collections."""
    try:
        db = await _get_db()
        summary = DashboardSummary()

        # Campaign stats
        campaign_query = {"user_id": user_id} if user_id else {}
        summary.total_campaigns = await db.campaigns.count_documents(campaign_query)
        summary.active_campaigns = await db.campaigns.count_documents({
            **campaign_query, "status": {"$in": ["running", "active", "in_progress"]}
        })

        # Lead stats
        lead_query = {"user_id": user_id} if user_id else {}
        summary.total_leads = await db.leads.count_documents(lead_query)

        # Email stats
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        email_query = {"user_id": user_id} if user_id else {}
        summary.emails_sent_total = await db.emails.count_documents(email_query) if hasattr(db, "emails") else 0
        summary.emails_sent_today = await db.emails.count_documents({
            **email_query, "created_at": {"$gte": today_start}
        }) if hasattr(db, "emails") else 0

        # Reply stats
        reply_query = {"user_id": user_id} if user_id else {}
        summary.replies_received = await db.replies.count_documents(reply_query) if hasattr(db, "replies") else 0

        # Task stats
        summary.pending_tasks = await db.tasks.count_documents({
            **lead_query, "status": {"$in": ["pending", "todo"]}
        }) if hasattr(db, "tasks") else 0

        # Recent activity
        activity_cursor = db.activity_logs.find(
            {} if not user_id else {"user_id": user_id}
        ).sort("created_at", -1).limit(10)
        summary.recent_activity = await activity_cursor.to_list(length=10)

        return summary
    except Exception as exc:
        logger.error("Failed to get dashboard summary: %s", exc)
        return DashboardSummary()


async def get_campaign_summaries(user_id: str = "") -> List[CampaignSummary]:
    """Get summary stats for each campaign."""
    try:
        db = await _get_db()
        query = {"user_id": user_id} if user_id else {}
        campaigns = await db.campaigns.find(query).sort("created_at", -1).limit(20).to_list(length=20)

        summaries = []
        for c in campaigns:
            cid = c.get("id", "")
            lead_count = await db.leads.count_documents({"campaign_id": cid}) if hasattr(db, "leads") else 0

            summaries.append(CampaignSummary(
                campaign_id=cid,
                name=c.get("name", ""),
                status=c.get("status", ""),
                total_leads=lead_count,
                created_at=str(c.get("created_at", "")),
                updated_at=str(c.get("updated_at", "")),
            ))
        return summaries
    except Exception as exc:
        logger.error("Failed to get campaign summaries: %s", exc)
        return []


async def get_lead_stats(user_id: str = "") -> Dict[str, Any]:
    """Get lead status breakdown."""
    try:
        db = await _get_db()
        query = {"user_id": user_id} if user_id else {}
        total = await db.leads.count_documents(query)

        pipeline = [
            {"$match": query},
            {"$group": {"_id": "$status", "count": {"$sum": 1}}},
        ]
        status_breakdown = {}
        if hasattr(db.leads, "aggregate"):
            async for doc in db.leads.aggregate(pipeline):
                status_breakdown[doc["_id"]] = doc["count"]

        return {"total": total, "by_status": status_breakdown}
    except Exception as exc:
        logger.error("Failed to get lead stats: %s", exc)
        return {"total": 0, "by_status": {}}


async def get_email_stats(user_id: str = "") -> Dict[str, Any]:
    """Get email delivery statistics."""
    try:
        db = await _get_db()
        query = {"user_id": user_id} if user_id else {}

        stats = {"total": 0, "sent": 0, "delivered": 0, "opened": 0, "clicked": 0, "replied": 0, "failed": 0}
        if hasattr(db, "emails"):
            stats["total"] = await db.emails.count_documents(query)
            for status in ["sent", "delivered", "opened", "clicked", "replied", "failed"]:
                stats[status] = await db.emails.count_documents({**query, "status": status})

        return stats
    except Exception as exc:
        logger.error("Failed to get email stats: %s", exc)
        return {"total": 0}


async def get_execution_logs(
    campaign_id: str = "",
    lead_id: str = "",
    module: str = "",
    limit: int = 50,
    offset: int = 0,
) -> List[ExecutionLog]:
    """Get execution logs with optional filters."""
    try:
        db = await _get_db()
        query: Dict[str, Any] = {}
        if campaign_id:
            query["campaign_id"] = campaign_id
        if lead_id:
            query["lead_id"] = lead_id
        if module:
            query["module"] = module

        cursor = db.execution_logs.find(query).sort("timestamp", -1).skip(offset).limit(limit)
        logs = await cursor.to_list(length=limit)
        return [
            ExecutionLog(
                execution_id=doc.get("execution_id", ""),
                campaign_id=doc.get("campaign_id", ""),
                lead_id=doc.get("lead_id", ""),
                module=doc.get("module", ""),
                status=doc.get("status", ""),
                message=doc.get("message", ""),
                metadata=doc.get("metadata", {}),
                timestamp=doc.get("timestamp", ""),
            )
            for doc in logs
        ]
    except Exception as exc:
        logger.error("Failed to get execution logs: %s", exc)
        return []
