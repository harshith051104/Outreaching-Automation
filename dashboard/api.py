"""
Dashboard API — router assembly and WebSocket endpoint.

Assembles all dashboard REST routers and the WebSocket gateway.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, Optional, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from dashboard.websocket_manager import dashboard_ws_manager
from dashboard.event_router import event_router
from dashboard.health_service import get_system_health
from dashboard.dashboard_service import (
    get_dashboard_summary, get_lead_stats, get_email_stats, get_execution_logs,
)
from dashboard.notification_service import (
    get_notifications, get_unread_count, mark_read, mark_all_read,
)
from dashboard.activity_feed import get_activity_feed
from dashboard.metrics import metrics_collector
from dashboard.campaign_api import router as campaign_router
from dashboard.analytics_api import router as analytics_router

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

# Include sub-routers
router.include_router(campaign_router)
router.include_router(analytics_router)


# ── REST Endpoints ──────────────────────────────────────────────────────

@router.get("/summary")
async def dashboard_summary(user_id: str = Query(default="")) -> Dict[str, Any]:
    summary = await get_dashboard_summary(user_id)
    return summary.to_dict()


@router.get("/health")
async def dashboard_health() -> Dict[str, Any]:
    health = await get_system_health()
    return health.to_dict()


@router.get("/leads/stats")
async def lead_statistics(user_id: str = Query(default="")) -> Dict[str, Any]:
    return await get_lead_stats(user_id)


@router.get("/emails/stats")
async def email_statistics(user_id: str = Query(default="")) -> Dict[str, Any]:
    return await get_email_stats(user_id)


@router.get("/activity")
async def activity(
    user_id: str = Query(default=""),
    limit: int = Query(default=50, le=200),
) -> Dict[str, Any]:
    items = await get_activity_feed(user_id=user_id, limit=limit)
    return {"activity": [i.to_dict() for i in items], "total": len(items)}


@router.get("/notifications")
async def notifications(
    user_id: str = Query(default=""),
    unread_only: bool = Query(default=False),
    limit: int = Query(default=50, le=200),
) -> Dict[str, Any]:
    items = await get_notifications(user_id, unread_only=unread_only, limit=limit)
    unread = await get_unread_count(user_id)
    return {"notifications": [n.to_dict() for n in items], "unread_count": unread}


@router.get("/notifications/unread-count")
async def notification_unread_count(user_id: str = Query(default="")) -> Dict[str, Any]:
    count = await get_unread_count(user_id)
    return {"unread_count": count}


@router.patch("/notifications/{notification_id}/read")
async def notification_mark_read(user_id: str, notification_id: str) -> Dict[str, Any]:
    success = await mark_read(user_id, notification_id)
    return {"success": success}


@router.post("/notifications/read-all")
async def notification_mark_all_read(user_id: str) -> Dict[str, Any]:
    count = await mark_all_read(user_id)
    return {"updated": count}


@router.get("/logs")
async def execution_logs(
    campaign_id: str = Query(default=""),
    lead_id: str = Query(default=""),
    module: str = Query(default=""),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0),
) -> Dict[str, Any]:
    logs = await get_execution_logs(campaign_id, lead_id, module, limit, offset)
    return {"logs": [l.to_dict() for l in logs], "total": len(logs)}


@router.get("/metrics")
async def dashboard_metrics() -> Dict[str, Any]:
    return metrics_collector.get_dict()


# ── WebSocket Endpoint ──────────────────────────────────────────────────

@router.websocket("/ws/{user_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: str,
    subscriptions: str = Query(default=""),
) -> None:
    """
    WebSocket gateway for real-time dashboard updates.

    Query params:
        subscriptions: comma-separated list (e.g. "campaign.123,notifications,system")
    """
    sub_set: Set[str] = set()
    if subscriptions:
        sub_set = {s.strip() for s in subscriptions.split(",") if s.strip()}
    if not sub_set:
        sub_set = {"all"}

    connection_id = await dashboard_ws_manager.connect(websocket, user_id, sub_set)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            msg_type = msg.get("type", "")

            if msg_type == "ping":
                await websocket.send_json({"type": "pong", "timestamp": time.time()})
                await dashboard_ws_manager.handle_pong(user_id, connection_id)

            elif msg_type == "subscribe":
                new_subs = set(msg.get("subscriptions", []))
                if new_subs:
                    dashboard_ws_manager.update_subscriptions(user_id, connection_id, new_subs)

            elif msg_type == "unsubscribe":
                remove_subs = set(msg.get("subscriptions", []))
                sub_set -= remove_subs
                dashboard_ws_manager.update_subscriptions(user_id, connection_id, sub_set)

    except WebSocketDisconnect:
        dashboard_ws_manager.disconnect(websocket, user_id)
        logger.info("WS disconnected: user=%s", user_id)
    except Exception as exc:
        dashboard_ws_manager.disconnect(websocket, user_id)
        logger.error("WS error: user=%s err=%s", user_id, exc)
