"""
LinkedIn background tasks.
"""

import asyncio
import logging
from datetime import datetime, timezone
from app.config.redis_config import celery_app
from app.config.mongodb_config import get_database
from app.services.linkedin_connection_monitor import check_for_updates

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Run async coroutine synchronously inside Celery worker loop."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


@celery_app.task(name="app.tasks.linkedin_tasks.poll_linkedin_inbox")
def poll_linkedin_inbox():
    """Poll LinkedIn for accepted connections, new messages, and generate auto-reply drafts."""
    logger.info("Celery Task: Running LinkedIn connection and inbox monitoring...")
    result = _run_async(check_for_updates())
    logger.info("Celery Task: LinkedIn monitoring completed: %s", result)
    return result
