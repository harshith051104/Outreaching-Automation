"""
Reply subsystem data models.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class ReplyIntent(str, enum.Enum):
    """Reply intent classification — extended investor taxonomy."""
    INTERESTED = "interested"
    MEETING_REQUESTED = "meeting_requested"
    PITCH_DECK_REQUESTED = "pitch_deck_requested"
    DATA_ROOM_REQUESTED = "data_room_requested"
    MORE_INFO_REQUESTED = "more_info_requested"
    TECHNICAL_QUESTIONS = "technical_questions"
    FINANCIAL_QUESTIONS = "financial_questions"
    DUE_DILIGENCE_STARTED = "due_diligence_started"
    PARTNER_INTRO_REQUESTED = "partner_intro_requested"
    POSITIVE_RESPONSE = "positive_response"
    NEUTRAL_RESPONSE = "neutral_response"
    TIMING_NOT_RIGHT = "timing_not_right"
    FOLLOW_UP_LATER = "follow_up_later"
    NOT_INTERESTED = "not_interested"
    ALREADY_INVESTED = "already_invested"
    PASSED_ON_OPPORTUNITY = "passed_on_opportunity"
    WRONG_CONTACT = "wrong_contact"
    OUT_OF_OFFICE = "out_of_office"
    UNSUBSCRIBE = "unsubscribe"
    REFERRAL = "referral"
    SPAM = "spam"
    UNKNOWN = "unknown"


class Sentiment(str, enum.Enum):
    """Reply sentiment — independent of intent."""
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class LeadStatus(str, enum.Enum):
    """Lead lifecycle status."""
    ACTIVE = "active"
    REPLIED = "replied"
    INTERESTED = "interested"
    QUALIFIED = "qualified"
    MEETING_SCHEDULED = "meeting_scheduled"
    NOT_INTERESTED = "not_interested"
    CLOSED = "closed"
    DO_NOT_CONTACT = "do_not_contact"
    OUT_OF_OFFICE = "out_of_office"
    WRONG_CONTACT = "wrong_contact"


class WorkflowEventType(str, enum.Enum):
    """Events published by the reply subsystem."""
    REPLY_RECEIVED = "reply.received"
    INTENT_DETECTED = "intent.detected"
    MEETING_REQUESTED = "meeting.requested"
    DECK_REQUESTED = "deck.requested"
    DATA_ROOM_REQUESTED = "data_room.requested"
    DUE_DILIGENCE_STARTED = "due_diligence_started"
    CAMPAIGN_PAUSED = "campaign.paused"
    CAMPAIGN_STOPPED = "campaign.stopped"
    LEAD_UPDATED = "lead.updated"
    LEAD_QUALIFIED = "lead.qualified"
    FOLLOWUP_DELAYED = "followup.delayed"
    FOLLOWUP_CANCELLED = "followup.cancelled"
    REFERRAL_RECEIVED = "referral.received"
    UNSUBSCRIBE_RECEIVED = "unsubscribe.received"
    MANUAL_TASK_CREATED = "manual_task.created"


# ── Intent → LeadStatus mapping ────────────────────────────────────────
INTENT_LEAD_STATUS_MAP: Dict[ReplyIntent, LeadStatus] = {
    ReplyIntent.INTERESTED: LeadStatus.INTERESTED,
    ReplyIntent.MEETING_REQUESTED: LeadStatus.MEETING_SCHEDULED,
    ReplyIntent.PITCH_DECK_REQUESTED: LeadStatus.INTERESTED,
    ReplyIntent.DATA_ROOM_REQUESTED: LeadStatus.QUALIFIED,
    ReplyIntent.MORE_INFO_REQUESTED: LeadStatus.INTERESTED,
    ReplyIntent.TECHNICAL_QUESTIONS: LeadStatus.INTERESTED,
    ReplyIntent.FINANCIAL_QUESTIONS: LeadStatus.QUALIFIED,
    ReplyIntent.DUE_DILIGENCE_STARTED: LeadStatus.QUALIFIED,
    ReplyIntent.PARTNER_INTRO_REQUESTED: LeadStatus.INTERESTED,
    ReplyIntent.POSITIVE_RESPONSE: LeadStatus.INTERESTED,
    ReplyIntent.NEUTRAL_RESPONSE: LeadStatus.REPLIED,
    ReplyIntent.TIMING_NOT_RIGHT: LeadStatus.ACTIVE,
    ReplyIntent.FOLLOW_UP_LATER: LeadStatus.ACTIVE,
    ReplyIntent.NOT_INTERESTED: LeadStatus.NOT_INTERESTED,
    ReplyIntent.ALREADY_INVESTED: LeadStatus.CLOSED,
    ReplyIntent.PASSED_ON_OPPORTUNITY: LeadStatus.CLOSED,
    ReplyIntent.WRONG_CONTACT: LeadStatus.WRONG_CONTACT,
    ReplyIntent.OUT_OF_OFFICE: LeadStatus.OUT_OF_OFFICE,
    ReplyIntent.UNSUBSCRIBE: LeadStatus.DO_NOT_CONTACT,
    ReplyIntent.REFERRAL: LeadStatus.INTERESTED,
    ReplyIntent.SPAM: LeadStatus.DO_NOT_CONTACT,
    ReplyIntent.UNKNOWN: LeadStatus.REPLIED,
}

# ── Intent → Campaign action ───────────────────────────────────────────
# Actions: "stop", "pause", "delay", "continue", "notify", "manual_task"
INTENT_CAMPAIGN_ACTION: Dict[ReplyIntent, Dict[str, Any]] = {
    ReplyIntent.INTERESTED: {"action": "stop", "notify": True},
    ReplyIntent.MEETING_REQUESTED: {"action": "stop", "notify": True, "create_task": True},
    ReplyIntent.PITCH_DECK_REQUESTED: {"action": "pause", "notify": True, "create_task": True},
    ReplyIntent.DATA_ROOM_REQUESTED: {"action": "pause", "notify": True, "create_task": True},
    ReplyIntent.MORE_INFO_REQUESTED: {"action": "stop", "notify": True},
    ReplyIntent.TECHNICAL_QUESTIONS: {"action": "stop", "notify": True, "create_task": True},
    ReplyIntent.FINANCIAL_QUESTIONS: {"action": "pause", "notify": True, "create_task": True},
    ReplyIntent.DUE_DILIGENCE_STARTED: {"action": "pause", "notify": True},
    ReplyIntent.PARTNER_INTRO_REQUESTED: {"action": "stop", "notify": True, "create_task": True},
    ReplyIntent.POSITIVE_RESPONSE: {"action": "stop", "notify": True},
    ReplyIntent.NEUTRAL_RESPONSE: {"action": "continue", "notify": False},
    ReplyIntent.TIMING_NOT_RIGHT: {"action": "delay", "delay_days": 30, "notify": False},
    ReplyIntent.FOLLOW_UP_LATER: {"action": "delay", "delay_days": 14, "notify": False},
    ReplyIntent.NOT_INTERESTED: {"action": "stop", "notify": True},
    ReplyIntent.ALREADY_INVESTED: {"action": "stop", "notify": True},
    ReplyIntent.PASSED_ON_OPPORTUNITY: {"action": "stop", "notify": True},
    ReplyIntent.WRONG_CONTACT: {"action": "stop", "notify": True},
    ReplyIntent.OUT_OF_OFFICE: {"action": "delay", "delay_days": 7, "notify": False},
    ReplyIntent.UNSUBSCRIBE: {"action": "stop", "notify": True},
    ReplyIntent.REFERRAL: {"action": "stop", "notify": True, "create_task": True},
    ReplyIntent.SPAM: {"action": "stop", "notify": False},
    ReplyIntent.UNKNOWN: {"action": "continue", "notify": True},
}


@dataclass
class ReplyRecord:
    """A parsed and analyzed reply stored in MongoDB."""
    id: str = ""
    email_id: str = ""
    campaign_id: str = ""
    lead_id: str = ""
    user_id: str = ""
    gmail_message_id: str = ""
    gmail_thread_id: str = ""
    sender_email: str = ""
    subject: str = ""
    raw_body: str = ""
    clean_text: str = ""
    attachments: List[Dict[str, Any]] = field(default_factory=list)
    received_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_doc(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "email_id": self.email_id,
            "campaign_id": self.campaign_id,
            "lead_id": self.lead_id,
            "user_id": self.user_id,
            "gmail_message_id": self.gmail_message_id,
            "gmail_thread_id": self.gmail_thread_id,
            "sender_email": self.sender_email,
            "subject": self.subject,
            "raw_body": self.raw_body,
            "clean_text": self.clean_text,
            "attachments": self.attachments,
            "received_at": self.received_at,
            "created_at": self.created_at,
        }

    @classmethod
    def from_doc(cls, doc: Dict[str, Any]) -> "ReplyRecord":
        return cls(
            id=doc.get("id", ""),
            email_id=doc.get("email_id", ""),
            campaign_id=doc.get("campaign_id", ""),
            lead_id=doc.get("lead_id", ""),
            user_id=doc.get("user_id", ""),
            gmail_message_id=doc.get("gmail_message_id", ""),
            gmail_thread_id=doc.get("gmail_thread_id", ""),
            sender_email=doc.get("sender_email", ""),
            subject=doc.get("subject", ""),
            raw_body=doc.get("raw_body", ""),
            clean_text=doc.get("clean_text", ""),
            attachments=doc.get("attachments", []),
            received_at=doc.get("received_at"),
            created_at=doc.get("created_at", datetime.now(timezone.utc)),
        )


@dataclass
class ReplySummary:
    """AI-generated summary of a reply."""
    summary: str = ""
    action_items: List[str] = field(default_factory=list)
    priority: str = "medium"  # high, medium, low
    key_topics: List[str] = field(default_factory=list)


@dataclass
class AnalysisResult:
    """Full analysis result for a reply."""
    intent: ReplyIntent = ReplyIntent.UNKNOWN
    intent_confidence: float = 0.0
    intent_reasoning: str = ""
    sentiment: Sentiment = Sentiment.NEUTRAL
    sentiment_confidence: float = 0.0
    lead_score_delta: float = 0.0
    key_signals: List[str] = field(default_factory=list)
    recommended_action: str = ""
    urgency: str = "low"
    summary: Optional[ReplySummary] = None

    def to_doc(self) -> Dict[str, Any]:
        return {
            "intent": self.intent.value,
            "intent_confidence": self.intent_confidence,
            "intent_reasoning": self.intent_reasoning,
            "sentiment": self.sentiment.value,
            "sentiment_confidence": self.sentiment_confidence,
            "lead_score_delta": self.lead_score_delta,
            "key_signals": self.key_signals,
            "recommended_action": self.recommended_action,
            "urgency": self.urgency,
            "summary": {
                "summary": self.summary.summary,
                "action_items": self.summary.action_items,
                "priority": self.summary.priority,
                "key_topics": self.summary.key_topics,
            } if self.summary else None,
        }

    @classmethod
    def from_doc(cls, doc: Dict[str, Any]) -> "AnalysisResult":
        summary_doc = doc.get("summary")
        summary = None
        if summary_doc:
            summary = ReplySummary(
                summary=summary_doc.get("summary", ""),
                action_items=summary_doc.get("action_items", []),
                priority=summary_doc.get("priority", "medium"),
                key_topics=summary_doc.get("key_topics", []),
            )
        return cls(
            intent=ReplyIntent(doc.get("intent", "unknown")),
            intent_confidence=doc.get("intent_confidence", 0.0),
            intent_reasoning=doc.get("intent_reasoning", ""),
            sentiment=Sentiment(doc.get("sentiment", "neutral")),
            sentiment_confidence=doc.get("sentiment_confidence", 0.0),
            lead_score_delta=doc.get("lead_score_delta", 0.0),
            key_signals=doc.get("key_signals", []),
            recommended_action=doc.get("recommended_action", ""),
            urgency=doc.get("urgency", "low"),
            summary=summary,
        )


@dataclass
class Decision:
    """Campaign decision based on intent analysis."""
    campaign_action: str = "continue"  # stop, pause, delay, continue
    delay_days: int = 0
    lead_status: LeadStatus = LeadStatus.REPLIED
    notify_user: bool = False
    create_manual_task: bool = False
    cancel_followups: bool = False
    workflow_events: List[WorkflowEvent] = field(default_factory=list)


@dataclass
class WorkflowEvent:
    """Event to be published to downstream systems."""
    event_type: WorkflowEventType = WorkflowEventType.REPLY_RECEIVED
    campaign_id: str = ""
    lead_id: str = ""
    user_id: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_doc(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type.value,
            "campaign_id": self.campaign_id,
            "lead_id": self.lead_id,
            "user_id": self.user_id,
            "data": self.data,
            "timestamp": self.timestamp,
        }
