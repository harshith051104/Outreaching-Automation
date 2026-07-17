"""
Dashboard API & WebSocket System.

Real-time communication layer for the outreach platform.
"""

from dashboard.models import (
    EventType, NotificationSeverity, HealthStatus, SubscriptionScope,
    WSEvent, DashboardNotification, ActivityItem, ComponentHealth,
    SystemHealth, CampaignSummary, DashboardSummary, ExecutionLog,
    DashboardMetrics,
)
from dashboard.config import DashboardConfig, dashboard_config
from dashboard.websocket_manager import DashboardWebSocketManager, dashboard_ws_manager
from dashboard.event_router import EventRouter, event_router
from dashboard.dashboard_service import (
    get_dashboard_summary, get_campaign_summaries, get_lead_stats,
    get_email_stats, get_execution_logs,
)
from dashboard.notification_service import (
    create_notification, get_notifications, get_unread_count,
    mark_read, mark_all_read, delete_notification,
)
from dashboard.activity_feed import (
    record_activity, get_activity_feed, broadcast_campaign_activity,
)
from dashboard.health_service import get_system_health
from dashboard.metrics import MetricsCollector, metrics_collector

__all__ = [
    # Models
    "EventType", "NotificationSeverity", "HealthStatus", "SubscriptionScope",
    "WSEvent", "DashboardNotification", "ActivityItem", "ComponentHealth",
    "SystemHealth", "CampaignSummary", "DashboardSummary", "ExecutionLog",
    "DashboardMetrics",
    # Config
    "DashboardConfig", "dashboard_config",
    # WebSocket
    "DashboardWebSocketManager", "dashboard_ws_manager",
    # Event Router
    "EventRouter", "event_router",
    # Services
    "get_dashboard_summary", "get_campaign_summaries", "get_lead_stats",
    "get_email_stats", "get_execution_logs",
    # Notifications
    "create_notification", "get_notifications", "get_unread_count",
    "mark_read", "mark_all_read", "delete_notification",
    # Activity
    "record_activity", "get_activity_feed", "broadcast_campaign_activity",
    # Health
    "get_system_health",
    # Metrics
    "MetricsCollector", "metrics_collector",
]
