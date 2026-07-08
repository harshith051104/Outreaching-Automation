"""
Pydantic schemas for email-related endpoints.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field


class EmailCreate(BaseModel):
    """Manual email creation payload."""
    campaign_id: str
    lead_id: str
    subject: str = Field(..., min_length=1, max_length=500)
    body_html: str
    gmail_account_id: str = ""
    to: str = ""
    sequence_number: int = 1
    attachments: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="List of attachments with 'filename', 'content' (base64), 'content_type' keys"
    )
    guardrail: Optional[Dict[str, Any]] = None
    correlation_id: Optional[str] = None


class EmailResponse(BaseModel):
    """Full email representation returned by the API."""
    id: str
    campaign_id: str
    lead_id: str
    user_id: str
    gmail_account_id: str
    subject: str
    body_html: str
    body_text: str
    tracking_id: str
    gmail_message_id: str
    gmail_thread_id: str
    status: str
    sequence_number: int
    sent_at: Optional[datetime] = None
    created_at: datetime


class GenerateEmailRequest(BaseModel):
    """Request body for AI-powered email generation."""
    lead_id: str
    campaign_id: str
    tone: str = "professional"
    custom_instructions: str = ""