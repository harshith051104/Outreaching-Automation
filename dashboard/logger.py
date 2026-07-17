"""
Structured logging for the dashboard subsystem.
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Any, Dict, Generator


def get_logger(name: str = "dashboard") -> logging.Logger:
    return logging.getLogger(name)


@contextmanager
def log_ws_operation(
    operation: str,
    user_id: str = "",
    connection_id: str = "",
    **extra: Any,
) -> Generator[Dict[str, Any], None, None]:
    logger = get_logger()
    start = time.time()
    ctx: Dict[str, Any] = {
        "operation": operation,
        "user_id": user_id,
        "connection_id": connection_id,
        **extra,
    }
    try:
        yield ctx
        elapsed_ms = (time.time() - start) * 1000
        ctx["latency_ms"] = round(elapsed_ms, 2)
        ctx["status"] = "success"
    except Exception as exc:
        elapsed_ms = (time.time() - start) * 1000
        ctx["latency_ms"] = round(elapsed_ms, 2)
        ctx["status"] = "error"
        ctx["error"] = str(exc)
        raise


def log_event_broadcast(
    event_type: str,
    user_count: int,
    latency_ms: float = 0.0,
) -> None:
    get_logger().info(
        "dashboard.event.broadcast",
        extra={
            "event_type": event_type,
            "user_count": user_count,
            "latency_ms": round(latency_ms, 2),
        },
    )


def log_api_request(
    method: str,
    path: str,
    status_code: int,
    latency_ms: float,
    user_id: str = "",
) -> None:
    get_logger().info(
        "dashboard.api.request",
        extra={
            "method": method,
            "path": path,
            "status_code": status_code,
            "latency_ms": round(latency_ms, 2),
            "user_id": user_id,
        },
    )


def log_notification_push(user_id: str, notification_type: str) -> None:
    get_logger().debug(
        "dashboard.notification.push",
        extra={"user_id": user_id, "type": notification_type},
    )
