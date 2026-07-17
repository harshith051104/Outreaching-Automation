"""
Email subsystem data models and state machine.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional


class EmailStatus(str, enum.Enum):
    """Full email lifecycle states."""
    CREATED = "created"
    READY = "ready"
    SENDING = "sending"
    SENT = "sent"
    DELIVERED = "delivered"
    OPENED = "opened"
    CLICKED = "clicked"
    REPLIED = "replied"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"

    @classmethod
    def valid_transitions(cls) -> Dict[str, set[str]]:
        return {
            cls.CREATED.value: {cls.READY.value, cls.CANCELLED.value, cls.FAILED.value},
            cls.READY.value: {cls.SENDING.value, cls.CANCELLED.value, cls.FAILED.value},
            cls.SENDING.value: {cls.SENT.value, cls.FAILED.value},
            cls.SENT.value: {cls.DELIVERED.value, cls.FAILED.value, cls.OPENED.value, cls.CLICKED.value, cls.REPLIED.value},
            cls.DELIVERED.value: {cls.OPENED.value, cls.CLICKED.value, cls.REPLIED.value, cls.FAILED.value},
            cls.OPENED.value: {cls.CLICKED.value, cls.REPLIED.value, cls.DELIVERED.value},
            cls.CLICKED.value: {cls.REPLIED.value, cls.OPENED.value},
            cls.REPLIED.value: set(),
            cls.FAILED.value: {cls.READY.value},
            cls.CANCELLED.value: set(),
            cls.PAUSED.value: {cls.READY.value, cls.CANCELLED.value},
        }

    def can_transition_to(self, target: "EmailStatus") -> bool:
        return target.value in self.valid_transitions().get(self.value, set())


class RetryPolicy(str, enum.Enum):
    """Retry backoff strategies."""
    NONE = "none"
    FIXED = "fixed"
    EXPONENTIAL = "exponential"
    EXPONENTIAL_JITTER = "exponential_jitter"


@dataclass
class EmailRecord:
    """Email document stored in MongoDB. Mirrors existing schema for backward compat."""
    id: str = ""
    user_id: str = ""
    campaign_id: str = ""
    lead_id: str = ""
    gmail_account_id: str = ""
    to: str = ""
    subject: str = ""
    body_html: str = ""
    tracking_id: str = ""
    sequence_number: int = 1
    attachments: list[Dict[str, Any]] = field(default_factory=list)
    status: str = EmailStatus.CREATED.value
    gmail_message_id: Optional[str] = None
    gmail_thread_id: Optional[str] = None
    sent_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    error_message: Optional[str] = None
    retry_count: int = 0
    next_retry_at: Optional[datetime] = None
    guardrail: Optional[Dict[str, Any]] = None
    correlation_id: Optional[str] = None

    def to_doc(self) -> Dict[str, Any]:
        doc = {
            "id": self.id,
            "user_id": self.user_id,
            "campaign_id": self.campaign_id,
            "lead_id": self.lead_id,
            "gmail_account_id": self.gmail_account_id,
            "to": self.to,
            "subject": self.subject,
            "body_html": self.body_html,
            "tracking_id": self.tracking_id,
            "sequence_number": self.sequence_number,
            "attachments": self.attachments,
            "status": self.status,
            "gmail_message_id": self.gmail_message_id,
            "gmail_thread_id": self.gmail_thread_id,
            "sent_at": self.sent_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "retry_count": self.retry_count,
            "next_retry_at": self.next_retry_at,
            "guardrail": self.guardrail,
            "correlation_id": self.correlation_id,
        }
        if self.error_message:
            doc["error_message"] = self.error_message
        return doc

    @classmethod
    def from_doc(cls, doc: Dict[str, Any]) -> "EmailRecord":
        return cls(
            id=doc.get("id", ""),
            user_id=doc.get("user_id", ""),
            campaign_id=doc.get("campaign_id", ""),
            lead_id=doc.get("lead_id", ""),
            gmail_account_id=doc.get("gmail_account_id", ""),
            to=doc.get("to", ""),
            subject=doc.get("subject", ""),
            body_html=doc.get("body_html", ""),
            tracking_id=doc.get("tracking_id", ""),
            sequence_number=doc.get("sequence_number", 1),
            attachments=doc.get("attachments", []),
            status=doc.get("status", EmailStatus.CREATED.value),
            gmail_message_id=doc.get("gmail_message_id"),
            gmail_thread_id=doc.get("gmail_thread_id"),
            sent_at=doc.get("sent_at"),
            created_at=doc.get("created_at", datetime.now(timezone.utc)),
            updated_at=doc.get("updated_at", datetime.now(timezone.utc)),
            error_message=doc.get("error_message"),
            retry_count=doc.get("retry_count", 0),
            next_retry_at=doc.get("next_retry_at"),
            guardrail=doc.get("guardrail"),
            correlation_id=doc.get("correlation_id"),
        )


@dataclass
class TrackingEvent:
    """Single tracking event (open, click, reply, etc.)."""
    id: str = ""
    tracking_id: str = ""
    email_id: str = ""
    campaign_id: str = ""
    lead_id: str = ""
    event_type: str = ""
    ip_address: str = ""
    user_agent: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_doc(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "tracking_id": self.tracking_id,
            "email_id": self.email_id,
            "campaign_id": self.campaign_id,
            "lead_id": self.lead_id,
            "event_type": self.event_type,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_doc(cls, doc: Dict[str, Any]) -> "TrackingEvent":
        return cls(
            id=doc.get("id", ""),
            tracking_id=doc.get("tracking_id", ""),
            email_id=doc.get("email_id", ""),
            campaign_id=doc.get("campaign_id", ""),
            lead_id=doc.get("lead_id", ""),
            event_type=doc.get("event_type", ""),
            ip_address=doc.get("ip_address", ""),
            user_agent=doc.get("user_agent", ""),
            metadata=doc.get("metadata", {}),
            timestamp=doc.get("timestamp", datetime.now(timezone.utc)),
        )


@dataclass
class SendRequest:
    """Request to send a single email. Input to DeliveryManager.send()."""
    email_record: EmailRecord = field(default_factory=EmailRecord)
    body_html_with_tracking: str = ""
    thread_id: Optional[str] = None
    in_reply_to: Optional[str] = None
    references: Optional[str] = None
    attachments: Optional[list[Dict[str, Any]]] = None


@dataclass
class SendResult:
    """Result of a send attempt."""
    success: bool = False
    gmail_message_id: Optional[str] = None
    gmail_thread_id: Optional[str] = None
    label_ids: list[str] = field(default_factory=list)
    error: Optional[str] = None
    should_retry: bool = False
