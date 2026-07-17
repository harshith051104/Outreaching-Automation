"""
Analytics Dashboard API — read-only analytics endpoints.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Query

from dashboard.dashboard_service import get_email_stats, get_lead_stats

router = APIRouter(prefix="/analytics", tags=["dashboard-analytics"])


@router.get("/overview")
async def analytics_overview(user_id: str = Query(default="")) -> Dict[str, Any]:
    """Get analytics overview: email stats, lead stats."""
    email_stats = await get_email_stats(user_id)
    lead_stats = await get_lead_stats(user_id)
    return {
        "emails": email_stats,
        "leads": lead_stats,
    }


@router.get("/emails")
async def email_analytics(user_id: str = Query(default="")) -> Dict[str, Any]:
    """Get email delivery analytics."""
    return await get_email_stats(user_id)


@router.get("/leads")
async def lead_analytics(user_id: str = Query(default="")) -> Dict[str, Any]:
    """Get lead status analytics."""
    return await get_lead_stats(user_id)
