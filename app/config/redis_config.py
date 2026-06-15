"""
Redis and Celery configuration.

Sets up Celery app with Redis as broker and backend.
"""

from celery import Celery
from typing import Optional

try:
    from app.config.settings import settings

    celery_app = Celery(
        "outreach",
        broker=settings.REDIS_URL,
        backend=settings.REDIS_URL,
    )
except ImportError:
    celery_app: Optional[Celery] = None

__all__ = ["celery_app"]