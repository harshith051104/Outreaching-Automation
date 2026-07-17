# deprecated: removed from platform

import logging

logger = logging.getLogger(__name__)

async def import_leads_from_csv(*args, **kwargs):
    logger.warning("LinkedIn is removed from the platform. import_leads_from_csv called.")
    return []

def extract_linkedin_urls_from_text(*args, **kwargs):
    logger.warning("LinkedIn is removed from the platform. extract_linkedin_urls_from_text called.")
    return []

async def get_linkedin_leads_for_outreach(*args, **kwargs):
    logger.warning("LinkedIn is removed from the platform. get_linkedin_leads_for_outreach called.")
    return []

async def bulk_create_linkedin_actions(*args, **kwargs):
    logger.warning("LinkedIn is removed from the platform. bulk_create_linkedin_actions called.")
    return []