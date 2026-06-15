"""
Pydantic schemas for tracking / engagement endpoints.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class TrackingEventResponse(BaseModel):
    """Full tracking event returned by the API."""
    id: str
    tracking_id: str
    email_id: str
    campaign_id: str
    lead_id: str
    event_type: str
    ip_address: str
    user_agent: str
    url: str
    timestamp: datetime


class TrackingStats(BaseModel):
    """Aggregated tracking statistics for a campaign or lead."""
    total_opens: int = 0
    unique_opens: int = 0
    total_clicks: int = 0
    unique_clicks: int = 0
    total_replies: int = 0
