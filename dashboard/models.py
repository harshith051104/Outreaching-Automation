"""
Dashboard subsystem data models.

All types: WebSocket events, notifications, activity, health, metrics.
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# ── Enums ────────────────────────────────────────────────────────────────

class EventType(str, enum.Enum):
    """Standard WebSocket event types (domain.action format)."""
    # Campaign events
    CAMPAIGN_STARTED = "campaign.started"
    CAMPAIGN_PAUSED = "campaign.paused"
    CAMPAIGN_RESUMED = "campaign.resumed"
    CAMPAIGN_COMPLETED = "campaign.completed"
    CAMPAIGN_FAILED = "campaign.failed"
    CAMPAIGN_PROGRESS = "campaign.progress"

    # Lead events
    LEAD_UPDATED = "lead.updated"
    LEAD_PROCESSED = "lead.processed"

    # Email events
    EMAIL_SENT = "email.sent"
    EMAIL_FAILED = "email.failed"
    EMAIL_DELIVERED = "email.delivered"
    EMAIL_OPENED = "email.opened"
    EMAIL_CLICKED = "email.clicked"
    EMAIL_REPLIED = "email.replied"

    # Reply events
    REPLY_RECEIVED = "reply.received"
    REPLY_CLASSIFIED = "reply.classified"

    # AI events
    AI_STARTED = "ai.started"
    AI_PROGRESS = "ai.progress"
    AI_COMPLETED = "ai.completed"
    AI_FAILED = "ai.failed"

    # Notification events
    NOTIFICATION_CREATED = "notification.created"

    # System events
    SYSTEM_HEALTH = "system.health"
    WORKER_STATUS = "worker.status"

    # Dashboard events
    DASHBOARD_REFRESH = "dashboard.refresh"

    # Generic
    CUSTOM = "custom"


class NotificationSeverity(str, enum.Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    SUCCESS = "success"


class HealthStatus(str, enum.Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class SubscriptionScope(str, enum.Enum):
    """What a client can subscribe to."""
    ALL = "all"
    CAMPAIGN = "campaign"
    USER = "user"
    SYSTEM = "system"
    LOGS = "logs"


# ── WebSocket Event ─────────────────────────────────────────────────────

@dataclass
class WSEvent:
    """A WebSocket event to send to clients."""
    event_type: str
    data: Dict[str, Any]
    user_id: str = ""
    campaign_id: str = ""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "event_type": self.event_type,
            "data": self.data,
            "event_id": self.event_id,
            "timestamp": self.timestamp,
        }
        if self.campaign_id:
            d["campaign_id"] = self.campaign_id
        return d


# ── Notification ─────────────────────────────────────────────────────────

@dataclass
class DashboardNotification:
    """Dashboard notification (extends existing Notification model)."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    type: str = ""
    title: str = ""
    message: str = ""
    severity: NotificationSeverity = NotificationSeverity.INFO
    reference_id: str = ""
    reference_type: str = ""
    is_read: bool = False
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "type": self.type,
            "title": self.title,
            "message": self.message,
            "severity": self.severity.value,
            "reference_id": self.reference_id,
            "reference_type": self.reference_type,
            "is_read": self.is_read,
            "created_at": self.created_at,
        }


# ── Activity Item ────────────────────────────────────────────────────────

@dataclass
class ActivityItem:
    """Single activity feed entry."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    user_name: str = ""
    action: str = ""
    reference_id: str = ""
    reference_type: str = ""
    details: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "action": self.action,
            "reference_id": self.reference_id,
            "reference_type": self.reference_type,
            "details": self.details,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }


# ── Health Check ─────────────────────────────────────────────────────────

@dataclass
class ComponentHealth:
    """Health status of a single system component."""
    name: str
    status: HealthStatus
    latency_ms: float = 0.0
    message: str = ""
    last_checked: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "latency_ms": round(self.latency_ms, 2),
            "message": self.message,
            "last_checked": self.last_checked,
        }


@dataclass
class SystemHealth:
    """Aggregated system health."""
    status: HealthStatus = HealthStatus.UNKNOWN
    components: List[ComponentHealth] = field(default_factory=list)
    uptime_seconds: float = 0.0
    checked_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "components": [c.to_dict() for c in self.components],
            "uptime_seconds": round(self.uptime_seconds, 1),
            "checked_at": self.checked_at,
        }


# ── Dashboard Summary ───────────────────────────────────────────────────

@dataclass
class CampaignSummary:
    """Dashboard campaign summary."""
    campaign_id: str = ""
    name: str = ""
    status: str = ""
    total_leads: int = 0
    emails_sent: int = 0
    emails_opened: int = 0
    emails_clicked: int = 0
    emails_replied: int = 0
    emails_failed: int = 0
    progress_pct: float = 0.0
    health_score: float = 0.0
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "name": self.name,
            "status": self.status,
            "total_leads": self.total_leads,
            "emails_sent": self.emails_sent,
            "emails_opened": self.emails_opened,
            "emails_clicked": self.emails_clicked,
            "emails_replied": self.emails_replied,
            "emails_failed": self.emails_failed,
            "progress_pct": round(self.progress_pct, 1),
            "health_score": round(self.health_score, 1),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class DashboardSummary:
    """Top-level dashboard summary."""
    total_campaigns: int = 0
    active_campaigns: int = 0
    total_leads: int = 0
    emails_sent_today: int = 0
    emails_sent_total: int = 0
    replies_received: int = 0
    meetings_scheduled: int = 0
    pending_tasks: int = 0
    active_users: int = 0
    recent_activity: List[Dict[str, Any]] = field(default_factory=list)
    campaigns: List[CampaignSummary] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_campaigns": self.total_campaigns,
            "active_campaigns": self.active_campaigns,
            "total_leads": self.total_leads,
            "emails_sent_today": self.emails_sent_today,
            "emails_sent_total": self.emails_sent_total,
            "replies_received": self.replies_received,
            "meetings_scheduled": self.meetings_scheduled,
            "pending_tasks": self.pending_tasks,
            "active_users": self.active_users,
            "recent_activity": self.recent_activity,
            "campaigns": [c.to_dict() for c in self.campaigns],
        }


# ── Execution Log ────────────────────────────────────────────────────────

@dataclass
class ExecutionLog:
    """Single execution log entry."""
    execution_id: str = ""
    campaign_id: str = ""
    lead_id: str = ""
    module: str = ""
    status: str = ""
    message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "campaign_id": self.campaign_id,
            "lead_id": self.lead_id,
            "module": self.module,
            "status": self.status,
            "message": self.message,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }


# ── Dashboard Metrics ───────────────────────────────────────────────────

@dataclass
class DashboardMetrics:
    """Collected dashboard metrics."""
    ws_connections: int = 0
    ws_messages_sent: int = 0
    ws_messages_failed: int = 0
    api_requests: int = 0
    api_errors: int = 0
    events_routed: int = 0
    notifications_pushed: int = 0
    avg_api_latency_ms: float = 0.0
    avg_ws_latency_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ws_connections": self.ws_connections,
            "ws_messages_sent": self.ws_messages_sent,
            "ws_messages_failed": self.ws_messages_failed,
            "api_requests": self.api_requests,
            "api_errors": self.api_errors,
            "events_routed": self.events_routed,
            "notifications_pushed": self.notifications_pushed,
            "avg_api_latency_ms": round(self.avg_api_latency_ms, 2),
            "avg_ws_latency_ms": round(self.avg_ws_latency_ms, 2),
        }
