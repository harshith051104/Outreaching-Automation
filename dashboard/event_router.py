"""
Event Router — bridges EventBus to WebSocket, filters by subscriptions.

Subscribes to the orchestrator EventBus and routes matching events
to connected dashboard WebSocket clients.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Dict, List, Optional, Set

from dashboard.models import WSEvent, EventType
from dashboard.websocket_manager import dashboard_ws_manager
from dashboard.config import dashboard_config

logger = logging.getLogger(__name__)


class EventRouter:
    """
    Routes events from the EventBus to WebSocket clients.

    Subscribes to wildcard patterns on the EventBus, filters events
    by type and user/campaign scope, then pushes to WebSocket.
    """

    def __init__(self):
        self._event_bus: Optional[Any] = None
        self._routed_count = 0
        self._handler_map: Dict[str, Callable] = {}

    def attach_event_bus(self, event_bus: Any) -> None:
        """Attach to the orchestrator EventBus and subscribe to relevant topics."""
        self._event_bus = event_bus

        # Subscribe to all events with wildcard
        event_bus.subscribe("*", self._handle_event)

        # Also subscribe to specific patterns for logging
        for pattern in ["campaign.*", "email.*", "reply.*", "lead.*", "ai.*", "system.*"]:
            event_bus.subscribe(pattern, self._handle_event)

        logger.info("EventRouter attached to EventBus")

    async def _handle_event(self, topic: str, data: Dict[str, Any]) -> None:
        """Process an EventBus event and route to WebSocket."""
        event_type = data.get("topic", topic)
        user_id = data.get("user_id", "")
        campaign_id = data.get("campaign_id", "")

        # Map EventBus topics to standard event types
        mapped_type = self._map_event_type(event_type)

        # Skip events that don't map to dashboard events
        if not mapped_type:
            return

        # Skip events with no user targeting
        if not user_id and not campaign_id:
            return

        event = WSEvent(
            event_type=mapped_type,
            data=data,
            user_id=user_id,
            campaign_id=campaign_id,
        )

        start = time.time()

        if campaign_id:
            await dashboard_ws_manager.broadcast_to_campaign(campaign_id, event)
        elif user_id:
            await dashboard_ws_manager.send_to_user(user_id, event)

        elapsed_ms = (time.time() - start) * 1000
        self._routed_count += 1

    def _map_event_type(self, topic: str) -> Optional[str]:
        """Map EventBus topic to standard dashboard event type."""
        # Direct mapping
        direct_map = {
            "campaign.started": EventType.CAMPAIGN_STARTED.value,
            "campaign.paused": EventType.CAMPAIGN_PAUSED.value,
            "campaign.resumed": EventType.CAMPAIGN_RESUMED.value,
            "campaign.completed": EventType.CAMPAIGN_COMPLETED.value,
            "campaign.failed": EventType.CAMPAIGN_FAILED.value,
            "campaign.progress": EventType.CAMPAIGN_PROGRESS.value,
            "email.sent": EventType.EMAIL_SENT.value,
            "email.failed": EventType.EMAIL_FAILED.value,
            "email.delivered": EventType.EMAIL_DELIVERED.value,
            "email.opened": EventType.EMAIL_OPENED.value,
            "email.clicked": EventType.EMAIL_CLICKED.value,
            "reply.received": EventType.REPLY_RECEIVED.value,
            "reply.classified": EventType.REPLY_CLASSIFIED.value,
            "lead.updated": EventType.LEAD_UPDATED.value,
            "lead.processed": EventType.LEAD_PROCESSED.value,
            "ai.started": EventType.AI_STARTED.value,
            "ai.completed": EventType.AI_COMPLETED.value,
            "ai.failed": EventType.AI_FAILED.value,
            "system.health": EventType.SYSTEM_HEALTH.value,
            "worker.status": EventType.WORKER_STATUS.value,
        }
        if topic in direct_map:
            return direct_map[topic]

        # Prefix matching
        for prefix, event_type in [
            ("campaign.", EventType.CAMPAIGN_PROGRESS.value),
            ("email.", EventType.EMAIL_SENT.value),
            ("reply.", EventType.REPLY_RECEIVED.value),
            ("lead.", EventType.LEAD_UPDATED.value),
            ("ai.", EventType.AI_PROGRESS.value),
            ("step.", None),
            ("workflow.", None),
        ]:
            if topic.startswith(prefix) and event_type:
                return event_type

        return None

    def route_custom_event(
        self,
        event_type: str,
        data: Dict[str, Any],
        user_id: str = "",
        campaign_id: str = "",
    ) -> WSEvent:
        """Create and return a custom WSEvent (for direct publishing)."""
        return WSEvent(
            event_type=event_type,
            data=data,
            user_id=user_id,
            campaign_id=campaign_id,
        )

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "routed_count": self._routed_count,
            "attached": self._event_bus is not None,
        }


# Module-level singleton
event_router = EventRouter()
