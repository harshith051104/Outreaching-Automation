"""
Pydantic schemas for campaign CRUD operations.

Enhanced to support Instantly-style workflows:
- Multi-step email sequences with A/B testing variants
- Campaign scheduling with time windows and days
- Daily sending limits and throttling
- Stop-on-reply and auto-reply handling
- Open/link tracking
- Email account rotation
"""

from __future__ import annotations

from datetime import datetime, date, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class CampaignStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    SCHEDULED = "scheduled"


class StepType(str, Enum):
    EMAIL = "email"


class DelayUnit(str, Enum):
    MINUTES = "minutes"
    HOURS = "hours"
    DAYS = "days"


class NotSendingStatus(int, Enum):
    OUT_OF_SCHEDULE = 1
    WAITING_LEAD_PROCESS = 2
    DAILY_LIMIT_REACHED = 3
    ACCOUNTS_DAILY_LIMIT = 4
    ERROR = 99


class TimeWindow(BaseModel):
    """Daily time window for sending."""
    from_time: str = Field(..., pattern=r"^([01][0-9]|2[0-3]):([0-5][0-9])$", examples=["09:00"])
    to_time: str = Field(..., pattern=r"^([01][0-9]|2[0-3]):([0-5][0-9])$", examples=["17:00"])


class DaySchedule(BaseModel):
    """Schedule for a specific day configuration."""
    name: str = Field(..., description="Schedule name, e.g. 'Weekdays'")
    timing: TimeWindow
    days: dict[str, bool] = Field(
        ...,
        description="Day-of-week flags: 0=Sunday, 1=Monday, ..., 6=Saturday",
        examples=[{"0": False, "1": True, "2": True, "3": True, "4": True, "5": True, "6": False}],
    )
    timezone: str = Field(default="UTC", description="IANA timezone for this schedule")


class CampaignSchedule(BaseModel):
    """Campaign sending schedule."""
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    schedules: list[DaySchedule] = Field(..., min_length=1)


class EmailVariant(BaseModel):
    """A single email variant for A/B testing within a step."""
    subject: str
    body: str
    is_disabled: bool = Field(default=False, alias="v_disabled")

    model_config = {"populate_by_name": True}


class SequenceStep(BaseModel):
    """A single step in an email sequence."""
    type: StepType = StepType.EMAIL
    delay: int = Field(default=2, description="Delay before sending NEXT email")
    delay_unit: DelayUnit = DelayUnit.DAYS
    variants: list[EmailVariant] = Field(..., min_length=1, description="A/B test variants")


class CampaignSequence(BaseModel):
    """Email sequence (one sequence per campaign, with multiple steps)."""
    steps: list[SequenceStep] = Field(..., min_length=1)


class AutoVariantTrigger(str, Enum):
    REPLY_RATE = "reply_rate"
    CLICK_RATE = "click_rate"
    OPEN_RATE = "open_rate"


class AutoVariantSelect(BaseModel):
    """Auto-select winning variant based on metric."""
    trigger: AutoVariantTrigger


class CampaignSettings(BaseModel):
    """Comprehensive campaign settings matching Instantly-style config."""
    daily_limit: int = Field(default=50, description="Max emails per day across all accounts")
    daily_max_leads: Optional[int] = Field(default=None, description="Max new leads to contact per day")
    email_gap: int = Field(default=10, description="Gap between emails in minutes")
    random_wait_max: Optional[int] = Field(default=None, description="Random wait max in minutes")
    text_only: bool = Field(default=False, description="Send text-only emails (no HTML)")
    first_email_text_only: bool = Field(default=False, description="First email text-only, rest HTML")
    open_tracking: bool = Field(default=True, description="Track email opens")
    link_tracking: bool = Field(default=True, description="Track link clicks")
    stop_on_reply: bool = Field(default=False, description="Stop campaign when lead replies")
    stop_on_auto_reply: bool = Field(default=False, description="Stop on auto-reply (OOO, etc.)")
    stop_for_company: bool = Field(default=False, description="Stop entire company/domain on reply")
    insert_unsubscribe_header: bool = Field(default=False, description="Add unsubscribe header")
    allow_risky_contacts: bool = Field(default=False, description="Allow risky email addresses")
    disable_bounce_protect: bool = Field(default=False, description="Disable bounce protection")
    match_lead_esp: bool = Field(default=False, description="Match lead ESP to sender ESP")
    prioritize_new_leads: bool = Field(default=False, description="Prioritize new leads over existing")
    auto_variant_select: Optional[AutoVariantSelect] = None
    limit_emails_per_company: Optional[int] = Field(
        default=None,
        description="Max emails per company per day (overrides workspace default)",
    )
    cc_list: list[str] = Field(default_factory=list, description="CC email addresses")
    bcc_list: list[str] = Field(default_factory=list, description="BCC email addresses")


class WebhookEventType(str, Enum):
    EMAIL_SENT = "email_sent"
    EMAIL_OPENED = "email_opened"
    REPLY_RECEIVED = "reply_received"
    AUTO_REPLY_RECEIVED = "auto_reply_received"
    LINK_CLICKED = "link_clicked"
    EMAIL_BOUNCED = "email_bounced"
    LEAD_UNSUBSCRIBED = "lead_unsubscribed"
    ACCOUNT_ERROR = "account_error"
    CAMPAIGN_COMPLETED = "campaign_completed"
    LEAD_NEUTRAL = "lead_neutral"
    LEAD_INTERESTED = "lead_interested"
    LEAD_NOT_INTERESTED = "lead_not_interested"
    LEAD_MEETING_BOOKED = "lead_meeting_booked"
    LEAD_MEETING_COMPLETED = "lead_meeting_completed"
    LEAD_CLOSED = "lead_closed"
    LEAD_OUT_OF_OFFICE = "lead_out_of_office"
    LEAD_WRONG_PERSON = "lead_wrong_person"


class WebhookConfig(BaseModel):
    """Webhook subscription configuration."""
    url: str
    events: list[WebhookEventType]
    is_active: bool = True
    secret: Optional[str] = None


class BlockListEntry(BaseModel):
    """Blocked email or domain."""
    value: str = Field(..., description="Email address or domain to block")
    reason: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class LeadLabel(BaseModel):
    """Custom label for categorizing leads."""
    id: str
    name: str
    color: str = "#3B82F6"
    description: str = ""


class CampaignCreate(BaseModel):
    """POST /api/campaigns request body."""
    name: str = Field(..., min_length=1, max_length=300)
    description: str = ""
    sequences: list[CampaignSequence] = Field(
        default_factory=lambda: [CampaignSequence(steps=[
            SequenceStep(variants=[EmailVariant(subject="", body="")])
        ])],
        description="Email sequences with A/B variants",
    )
    campaign_schedule: CampaignSchedule = Field(
        default_factory=lambda: CampaignSchedule(
            schedules=[DaySchedule(
                name="Default",
                timing=TimeWindow(from_time="09:00", to_time="17:00"),
                days={"0": False, "1": True, "2": True, "3": True, "4": True, "5": True, "6": False},
                timezone="UTC",
            )]
        )
    )
    email_list: list[str] = Field(default_factory=list, description="Sender email addresses")
    email_tag_list: list[str] = Field(default_factory=list, description="Email account tags to use")
    settings: CampaignSettings = Field(default_factory=CampaignSettings)
    is_evergreen: bool = Field(default=False, description="Recycle leads through sequence")


class CampaignUpdate(BaseModel):
    """PATCH /api/campaigns/{id} request body – all fields optional."""
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[CampaignStatus] = None
    sequences: Optional[list[CampaignSequence]] = None
    campaign_schedule: Optional[CampaignSchedule] = None
    email_list: Optional[list[str]] = None
    email_tag_list: Optional[list[str]] = None
    settings: Optional[CampaignSettings] = None
    is_evergreen: Optional[bool] = None


class CampaignResponse(BaseModel):
    """Full campaign representation returned by the API."""
    id: str
    user_id: str
    name: str
    description: str
    status: CampaignStatus
    sequences: list[CampaignSequence]
    campaign_schedule: CampaignSchedule
    email_list: list[str]
    email_tag_list: list[str]
    settings: CampaignSettings
    total_leads: int = 0
    sent_count: int = 0
    open_count: int = 0
    click_count: int = 0
    reply_count: int = 0
    bounce_count: int = 0
    unsubscribe_count: int = 0
    open_rate: float = 0.0
    click_rate: float = 0.0
    reply_rate: float = 0.0
    bounce_rate: float = 0.0
    not_sending_status: Optional[NotSendingStatus] = None
    is_evergreen: bool = False
    created_at: datetime
    updated_at: datetime


class CampaignAnalytics(BaseModel):
    """Analytics response for a campaign."""
    campaign_id: str
    campaign_name: str
    total_leads: int = 0
    emails_sent: int = 0
    emails_delivered: int = 0
    emails_opened: int = 0
    unique_opens: int = 0
    emails_clicked: int = 0
    unique_clicks: int = 0
    emails_replied: int = 0
    emails_bounced: int = 0
    unsubscribes: int = 0
    delivery_rate: float = 0.0
    open_rate: float = 0.0
    click_rate: float = 0.0
    reply_rate: float = 0.0
    bounce_rate: float = 0.0
    unsubscribe_rate: float = 0.0
    click_to_open_rate: float = 0.0
    step_analytics: list[dict[str, Any]] = Field(default_factory=list)
    daily_analytics: list[dict[str, Any]] = Field(default_factory=list)
    health_status: str = "healthy"
    health_issues: list[str] = Field(default_factory=list)


class WebhookEventPayload(BaseModel):
    """Webhook event payload sent to configured URLs."""
    timestamp: str
    event_type: WebhookEventType
    workspace: str
    campaign_id: str
    campaign_name: str
    lead_email: Optional[str] = None
    email_account: Optional[str] = None
    step: Optional[int] = None
    variant: Optional[int] = None
    is_first: bool = True
    email_id: Optional[str] = None
    email_subject: Optional[str] = None
    email_text: Optional[str] = None
    email_html: Optional[str] = None
    reply_text_snippet: Optional[str] = None
    reply_subject: Optional[str] = None
    reply_text: Optional[str] = None
    reply_html: Optional[str] = None
    data: dict[str, Any] = Field(default_factory=dict)