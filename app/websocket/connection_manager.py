"""
WebSocket Connection Manager.

Manages real-time WebSocket connections for reply monitoring.
"""

import json
import logging
from typing import Any
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages active WebSocket connections per user."""

    def __init__(self):
        self._connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        """Accept a new WebSocket connection and register it."""
        await websocket.accept()
        if user_id not in self._connections:
            self._connections[user_id] = []
        self._connections[user_id].append(websocket)
        logger.info("WebSocket connected for user %s", user_id)

    def disconnect(self, websocket: WebSocket, user_id: str):
        """Remove a WebSocket connection."""
        if user_id in self._connections:
            self._connections[user_id] = [
                ws for ws in self._connections[user_id] if ws != websocket
            ]
            if not self._connections[user_id]:
                del self._connections[user_id]
        logger.info("WebSocket disconnected for user %s", user_id)

    async def send_to_user(self, user_id: str, message: dict[str, Any]):
        """Send a JSON message to all connections for a specific user."""
        if user_id not in self._connections:
            return

        dead_connections = []
        for websocket in self._connections[user_id]:
            try:
                await websocket.send_json(message)
            except Exception:
                dead_connections.append(websocket)

        for ws in dead_connections:
            self.disconnect(ws, user_id)

    async def broadcast_reply(self, user_id: str, reply_data: dict):
        """Send a new reply notification to a user."""
        await self.send_to_user(user_id, {
            "type": "new_reply",
            "data": reply_data,
        })

    async def broadcast_draft_ready(self, user_id: str, draft_data: dict):
        """Send a draft-ready notification to a user."""
        await self.send_to_user(user_id, {
            "type": "draft_ready",
            "data": draft_data,
        })

    async def broadcast_draft_sent(self, user_id: str, result: dict):
        """Notify user that a draft was sent."""
        await self.send_to_user(user_id, {
            "type": "draft_sent",
            "data": result,
        })

    def is_connected(self, user_id: str) -> bool:
        """Check if a user has any active connections."""
        return bool(self._connections.get(user_id))


manager = ConnectionManager()