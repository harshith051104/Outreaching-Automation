"""
Tracking tasks - Gmail reply polling.

Delegates to email_delivery.sync_engine for core logic,
preserving the Celery task wrapper for backward compatibility.
"""

import asyncio
import logging

from app.config.redis_config import celery_app

# Re-export the sync engine's poll function
from email_delivery.sync_engine import poll_gmail_replies  # noqa: F401

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Run async coroutine synchronously inside Celery worker loop."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


@celery_app.task(name="app.tasks.tracking_tasks.poll_gmail_replies")
def poll_gmail_replies_task():
    """Celery task wrapper for poll_gmail_replies."""
    logger.info("Celery Task: Running Gmail reply polling...")
    result = _run_async(poll_gmail_replies())
    logger.info("Celery Task: Gmail reply polling completed: %s", result)
    return result
