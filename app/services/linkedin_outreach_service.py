# deprecated: removed from platform

import logging

logger = logging.getLogger(__name__)

async def scrape_profile(*args, **kwargs):
    logger.warning("LinkedIn is removed from the platform. scrape_profile called.")
    return {}

async def get_pending_invitations(*args, **kwargs):
    logger.warning("LinkedIn is removed from the platform. get_pending_invitations called.")
    return []

async def get_session_status(*args, **kwargs):
    logger.warning("LinkedIn is removed from the platform. get_session_status called.")
    return "disconnected"

async def send_connection_request(*args, **kwargs):
    logger.warning("LinkedIn is removed from the platform. send_connection_request called.")
    return {"success": False, "error": "LinkedIn removed from platform"}

async def send_message(*args, **kwargs):
    logger.warning("LinkedIn is removed from the platform. send_message called.")
    return {"success": False, "error": "LinkedIn removed from platform"}

async def send_message_by_name(*args, **kwargs):
    logger.warning("LinkedIn is removed from the platform. send_message_by_name called.")
    return {"success": False, "error": "LinkedIn removed from platform"}

async def follow_profile(*args, **kwargs):
    logger.warning("LinkedIn is removed from the platform. follow_profile called.")
    return {"success": False, "error": "LinkedIn removed from platform"}
