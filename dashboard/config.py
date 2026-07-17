"""
Dashboard subsystem configuration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Set


@dataclass
class WebSocketConfig:
    """WebSocket connection settings."""
    max_connections_per_user: int = 5
    heartbeat_interval_seconds: int = 30
    connection_timeout_seconds: int = 60
    max_message_size_bytes: int = 65536
    reconnect_cooldown_seconds: int = 5


@dataclass
class RateLimitConfig:
    """Rate limiting for APIs and WebSockets."""
    api_requests_per_minute: int = 120
    ws_messages_per_minute: int = 60
    ws_broadcasts_per_minute: int = 30


@dataclass
class NotificationConfig:
    """Notification delivery settings."""
    max_notifications_per_user: int = 100
    retention_days: int = 30
    push_enabled: bool = True


@dataclass
class ActivityConfig:
    """Activity feed settings."""
    max_items_per_user: int = 200
    retention_days: int = 90
    push_enabled: bool = True


@dataclass
class DashboardConfig:
    """Top-level dashboard configuration."""
    ws: WebSocketConfig = field(default_factory=WebSocketConfig)
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)
    notification: NotificationConfig = field(default_factory=NotificationConfig)
    activity: ActivityConfig = field(default_factory=ActivityConfig)

    # Event routing
    campaign_events: Set[str] = field(default_factory=lambda: {
        "campaign.started", "campaign.paused", "campaign.resumed",
        "campaign.completed", "campaign.failed", "campaign.progress",
    })
    email_events: Set[str] = field(default_factory=lambda: {
        "email.sent", "email.failed", "email.delivered",
        "email.opened", "email.clicked", "email.replied",
    })
    lead_events: Set[str] = field(default_factory=lambda: {
        "lead.updated", "lead.processed",
    })
    reply_events: Set[str] = field(default_factory=lambda: {
        "reply.received", "reply.classified",
    })
    ai_events: Set[str] = field(default_factory=lambda: {
        "ai.started", "ai.progress", "ai.completed", "ai.failed",
    })
    system_events: Set[str] = field(default_factory=lambda: {
        "system.health", "worker.status",
    })


dashboard_config = DashboardConfig()
