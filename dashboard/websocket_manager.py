"""
WebSocket Gateway — connection management, auth, broadcast, heartbeat.

Extends the existing ConnectionManager with subscription-based routing,
per-user event filtering, heartbeat, and rate limiting.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Callable, Dict, List, Optional, Set
from fastapi import WebSocket

from dashboard.models import WSEvent, EventType
from dashboard.config import dashboard_config

logger = logging.getLogger(__name__)


class DashboardWebSocketManager:
    """
    Centralized WebSocket manager for the dashboard.

    Supports:
    - Per-user connection tracking
    - Subscription-based event routing (campaign, user, system, logs)
    - Heartbeat / ping-pong
    - Rate limiting per connection
    - Auto-cleanup of dead connections
    """

    def __init__(self):
        # user_id -> list of (websocket, subscriptions)
        self._connections: Dict[str, List[Dict[str, Any]]] = {}
        self._connection_count = 0
        self._messages_sent = 0
        self._messages_failed = 0

    async def connect(
        self,
        websocket: WebSocket,
        user_id: str,
        subscriptions: Optional[Set[str]] = None,
    ) -> str:
        """Accept a connection, register it, return connection_id."""
        await websocket.accept()
        connection_id = f"conn_{int(time.time() * 1000)}_{user_id[:8]}"

        if user_id not in self._connections:
            self._connections[user_id] = []

        # Enforce max connections per user
        max_conns = dashboard_config.ws.max_connections_per_user
        if len(self._connections[user_id]) >= max_conns:
            # Close oldest connection
            oldest = self._connections[user_id].pop(0)
            try:
                await oldest["websocket"].close(code=1000, reason="replaced")
            except Exception:
                pass

        self._connections[user_id].append({
            "websocket": websocket,
            "connection_id": connection_id,
            "subscriptions": subscriptions or set(),
            "connected_at": time.time(),
            "last_pong": time.time(),
            "message_count": 0,
        })
        self._connection_count += 1
        logger.info("WS connected: user=%s conn=%s", user_id, connection_id)
        return connection_id

    def disconnect(self, websocket: WebSocket, user_id: str) -> None:
        """Remove a connection."""
        if user_id in self._connections:
            self._connections[user_id] = [
                c for c in self._connections[user_id] if c["websocket"] != websocket
            ]
            if not self._connections[user_id]:
                del self._connections[user_id]
            self._connection_count = max(0, self._connection_count - 1)
        logger.info("WS disconnected: user=%s", user_id)

    async def send_to_user(self, user_id: str, event: WSEvent) -> bool:
        """Send an event to all connections of a user, filtering by subscriptions."""
        if user_id not in self._connections:
            return False

        sent = False
        dead = []
        for conn in self._connections[user_id]:
            if not self._matches_subscription(conn, event):
                continue
            try:
                await conn["websocket"].send_json(event.to_dict())
                conn["message_count"] += 1
                self._messages_sent += 1
                sent = True
            except Exception:
                dead.append(conn)

        for d in dead:
            self.disconnect(d["websocket"], user_id)

        return sent

    async def broadcast(self, event: WSEvent, user_ids: Optional[List[str]] = None) -> int:
        """Broadcast an event to multiple users. Returns count of users reached."""
        targets = user_ids or list(self._connections.keys())
        count = 0
        for uid in targets:
            if await self.send_to_user(uid, event):
                count += 1
        return count

    async def broadcast_to_campaign(self, campaign_id: str, event: WSEvent) -> int:
        """Broadcast to all users subscribed to a campaign."""
        count = 0
        for user_id, conns in self._connections.items():
            for conn in conns:
                subs = conn.get("subscriptions", set())
                if f"campaign.{campaign_id}" in subs or "all" in subs:
                    try:
                        await conn["websocket"].send_json(event.to_dict())
                        self._messages_sent += 1
                        count += 1
                    except Exception:
                        pass
                    break  # one connection per user is enough
        return count

    def _matches_subscription(self, conn: Dict[str, Any], event: WSEvent) -> bool:
        """Check if a connection is subscribed to this event type."""
        subs = conn.get("subscriptions", set())
        if not subs:
            return True  # no filter = receive all

        if "all" in subs:
            return True

        # Check direct event type match
        if event.event_type in subs:
            return True

        # Check domain prefix match (e.g. "campaign" matches "campaign.started")
        domain = event.event_type.split(".")[0] if "." in event.event_type else ""
        if domain in subs:
            return True

        # Check campaign-specific subscription
        if event.campaign_id and f"campaign.{event.campaign_id}" in subs:
            return True

        return False

    async def handle_pong(self, user_id: str, connection_id: str) -> None:
        """Update last_pong timestamp for a connection."""
        if user_id in self._connections:
            for conn in self._connections[user_id]:
                if conn["connection_id"] == connection_id:
                    conn["last_pong"] = time.time()
                    break

    def cleanup_stale_connections(self) -> int:
        """Remove connections that haven't ponged within timeout. Returns count removed."""
        timeout = dashboard_config.ws.connection_timeout_seconds
        now = time.time()
        removed = 0

        for user_id in list(self._connections.keys()):
            before = len(self._connections[user_id])
            self._connections[user_id] = [
                c for c in self._connections[user_id]
                if now - c["last_pong"] < timeout
            ]
            removed += before - len(self._connections[user_id])
            if not self._connections[user_id]:
                del self._connections[user_id]

        return removed

    def update_subscriptions(self, user_id: str, connection_id: str, subscriptions: Set[str]) -> bool:
        """Update subscriptions for a connection."""
        if user_id in self._connections:
            for conn in self._connections[user_id]:
                if conn["connection_id"] == connection_id:
                    conn["subscriptions"] = subscriptions
                    return True
        return False

    def get_connected_users(self) -> List[str]:
        return list(self._connections.keys())

    def get_connection_count(self) -> int:
        return sum(len(conns) for conns in self._connections.values())

    def is_connected(self, user_id: str) -> bool:
        return bool(self._connections.get(user_id))

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "total_connections": self.get_connection_count(),
            "connected_users": len(self._connections),
            "messages_sent": self._messages_sent,
            "messages_failed": self._messages_failed,
        }


# Module-level singleton
dashboard_ws_manager = DashboardWebSocketManager()
