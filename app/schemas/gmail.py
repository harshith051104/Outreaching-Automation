"""
Pydantic schemas for Gmail integration endpoints.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr


class GmailConnectResponse(BaseModel):
    """Returned when initiating the Gmail OAuth2 flow."""
    auth_url: str
    state: str


class GmailAccountResponse(BaseModel):
    """Public-facing Gmail account info (no tokens exposed)."""
    id: str
    email: str
    connected_at: datetime
    is_active: bool


class GmailMessageResponse(BaseModel):
    """Simplified representation of a Gmail message."""
    id: str
    thread_id: str
    subject: str
    from_email: str
    snippet: str
    date: Optional[str] = None


class SendEmailRequest(BaseModel):
    """Manual send-email-via-Gmail request."""
    to: EmailStr
    subject: str
    body_html: str
    gmail_account_id: str
