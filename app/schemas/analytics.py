"""
Pydantic schemas for analytics / dashboard endpoints.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AnalyticsResponse(BaseModel):
    """Full campaign analytics returned by the API."""
    id: str
    campaign_id: str
    user_id: str
    total_sent: int
    total_delivered: int
    total_opens: int
    unique_opens: int
    total_clicks: int
    unique_clicks: int
    total_replies: int
    positive_replies: int
    bounces: int
    open_rate: float
    click_rate: float
    reply_rate: float
    bounce_rate: float
    daily_stats: list[dict[str, Any]]
    updated_at: datetime


class DashboardStats(BaseModel):
    """High-level stats shown on the main dashboard."""
    total_campaigns: int = 0
    total_leads: int = 0
    total_sent: int = 0
    total_opens: int = 0
    total_clicks: int = 0
    total_replies: int = 0
    open_rate: float = 0.0
    click_rate: float = 0.0
    reply_rate: float = 0.0


class CampaignInsights(BaseModel):
    """AI-generated insights for a campaign."""
    summary: str = ""
    recommendations: list[str] = Field(default_factory=list)
    top_performing_leads: list[dict[str, Any]] = Field(default_factory=list)
