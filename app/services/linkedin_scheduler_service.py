# deprecated: removed from platform

import logging

logger = logging.getLogger(__name__)

async def increment_daily_count(*args, **kwargs):
    logger.warning("LinkedIn is removed from the platform. increment_daily_count called.")
    return 0

async def process_due_actions(*args, **kwargs):
    logger.warning("LinkedIn is removed from the platform. process_due_actions called.")
    return 0
