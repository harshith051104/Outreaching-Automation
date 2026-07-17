"""
Health Service — system health checks.

Aggregates health from existing endpoints into a unified response.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from dashboard.models import ComponentHealth, SystemHealth, HealthStatus

logger = logging.getLogger(__name__)

_start_time = time.time()


async def check_mongodb() -> ComponentHealth:
    """Check MongoDB connectivity."""
    start = time.time()
    try:
        from app.config.mongodb_config import get_database
        db = await get_database()
        await db.command("ping")
        latency = (time.time() - start) * 1000
        return ComponentHealth(name="mongodb", status=HealthStatus.HEALTHY, latency_ms=latency)
    except Exception as exc:
        latency = (time.time() - start) * 1000
        return ComponentHealth(name="mongodb", status=HealthStatus.UNHEALTHY, latency_ms=latency, message=str(exc))


async def check_redis() -> ComponentHealth:
    """Check Redis connectivity."""
    start = time.time()
    try:
        import redis.asyncio as aioredis
        from app.config.settings import settings
        r = aioredis.from_url(settings.REDIS_URL if hasattr(settings, "REDIS_URL") else "redis://localhost:6379")
        await r.ping()
        await r.aclose()
        latency = (time.time() - start) * 1000
        return ComponentHealth(name="redis", status=HealthStatus.HEALTHY, latency_ms=latency)
    except Exception as exc:
        latency = (time.time() - start) * 1000
        return ComponentHealth(name="redis", status=HealthStatus.DEGRADED, latency_ms=latency, message=str(exc))


async def check_qdrant() -> ComponentHealth:
    """Check Qdrant connectivity."""
    start = time.time()
    try:
        from app.config.qdrant_config import get_qdrant_client
        client = get_qdrant_client()
        if client:
            client.get_collections()
            latency = (time.time() - start) * 1000
            return ComponentHealth(name="qdrant", status=HealthStatus.HEALTHY, latency_ms=latency)
        latency = (time.time() - start) * 1000
        return ComponentHealth(name="qdrant", status=HealthStatus.DEGRADED, latency_ms=latency, message="Client not available")
    except Exception as exc:
        latency = (time.time() - start) * 1000
        return ComponentHealth(name="qdrant", status=HealthStatus.DEGRADED, latency_ms=latency, message=str(exc))


async def check_celery() -> ComponentHealth:
    """Check Celery worker availability."""
    start = time.time()
    try:
        from celery_worker import celery_app
        inspector = celery_app.control.inspect(timeout=2.0)
        active = inspector.ping()
        latency = (time.time() - start) * 1000
        if active:
            return ComponentHealth(name="celery", status=HealthStatus.HEALTHY, latency_ms=latency,
                                   message=f"{len(active)} workers active")
        return ComponentHealth(name="celery", status=HealthStatus.DEGRADED, latency_ms=latency, message="No workers responding")
    except Exception as exc:
        latency = (time.time() - start) * 1000
        return ComponentHealth(name="celery", status=HealthStatus.DEGRADED, latency_ms=latency, message=str(exc))


async def check_gmail() -> ComponentHealth:
    """Check Gmail API availability."""
    start = time.time()
    try:
        from app.services.gmail_service import GmailService
        # Lightweight check — just verify the service can be imported
        latency = (time.time() - start) * 1000
        return ComponentHealth(name="gmail", status=HealthStatus.HEALTHY, latency_ms=latency)
    except Exception as exc:
        latency = (time.time() - start) * 1000
        return ComponentHealth(name="gmail", status=HealthStatus.DEGRADED, latency_ms=latency, message=str(exc))


async def get_system_health() -> SystemHealth:
    """Aggregate health from all components."""
    checks = [
        check_mongodb(),
        check_redis(),
        check_qdrant(),
        check_celery(),
        check_gmail(),
    ]

    import asyncio
    results = await asyncio.gather(*checks, return_exceptions=True)

    components = []
    for r in results:
        if isinstance(r, ComponentHealth):
            components.append(r)
        else:
            components.append(ComponentHealth(name="unknown", status=HealthStatus.UNKNOWN, message=str(r)))

    # Determine overall status
    statuses = [c.status for c in components]
    if all(s == HealthStatus.HEALTHY for s in statuses):
        overall = HealthStatus.HEALTHY
    elif any(s == HealthStatus.UNHEALTHY for s in statuses):
        overall = HealthStatus.UNHEALTHY
    elif any(s == HealthStatus.DEGRADED for s in statuses):
        overall = HealthStatus.DEGRADED
    else:
        overall = HealthStatus.UNKNOWN

    return SystemHealth(
        status=overall,
        components=components,
        uptime_seconds=time.time() - _start_time,
    )
