"""
Campaign Dashboard API — read-only campaign endpoints.

All endpoints are read-oriented; state-changing operations remain
in the Campaign Runtime module.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query

from dashboard.dashboard_service import get_campaign_summaries, get_lead_stats, get_execution_logs
from dashboard.models import CampaignSummary, ExecutionLog

router = APIRouter(prefix="/campaigns", tags=["dashboard-campaigns"])


@router.get("/summary")
async def campaign_summary(user_id: str = Query(default="")) -> Dict[str, Any]:
    """Get summary stats for all campaigns."""
    summaries = await get_campaign_summaries(user_id)
    return {
        "campaigns": [s.to_dict() for s in summaries],
        "total": len(summaries),
    }


@router.get("/{campaign_id}/progress")
async def campaign_progress(campaign_id: str) -> Dict[str, Any]:
    """Get detailed progress for a single campaign."""
    try:
        from app.config.mongodb_config import get_database
        db = await get_database()
        campaign = await db.campaigns.find_one({"id": campaign_id})
        if not campaign:
            return {"error": "Campaign not found"}

        leads = await db.leads.count_documents({"campaign_id": campaign_id}) if hasattr(db, "leads") else 0

        return {
            "campaign_id": campaign_id,
            "name": campaign.get("name", ""),
            "status": campaign.get("status", ""),
            "total_leads": leads,
            "settings": campaign.get("settings", {}),
            "created_at": str(campaign.get("created_at", "")),
        }
    except Exception as exc:
        return {"error": str(exc)}


@router.get("/{campaign_id}/logs")
async def campaign_logs(
    campaign_id: str,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0),
) -> Dict[str, Any]:
    """Get execution logs for a campaign."""
    logs = await get_execution_logs(campaign_id=campaign_id, limit=limit, offset=offset)
    return {
        "logs": [l.to_dict() for l in logs],
        "total": len(logs),
    }
