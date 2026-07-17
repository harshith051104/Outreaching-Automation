import asyncio
import logging
import sys
import re
from datetime import datetime, timezone

# Add parent directory to path so we can import app modules
import sys
sys.path.append('.')

from app.config.mongodb_config import get_database
from app.config.settings import settings
from app.tasks.campaign_tasks import _format_template, _ai_generate_placeholders, _clear_cached_placeholders

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("CampaignTest")

async def test_verification():
    db = await get_database()
    
    # 1. Fetch user
    user = await db.users.find_one({"email": "testuser@example.com"})
    if not user:
        logger.error("Test user testuser@example.com not found. Please prepare the environment first.")
        sys.exit(1)
        
    user_id = user["id"]
    
    # 2. Fetch campaign
    campaign = await db.campaigns.find_one({"name": "Testing Works", "user_id": user_id})
    if not campaign:
        logger.error("Campaign 'Testing Works' not found. Please prepare the environment first.")
        sys.exit(1)
        
    campaign_id = campaign["id"]
    logger.info(f"Loaded campaign: {campaign['name']} (ID: {campaign_id})")
    
    # 3. Fetch leads
    leads = await db.leads.find({"campaign_id": campaign_id}).to_list(length=10)
    if not leads:
        logger.error("No leads found for the campaign.")
        sys.exit(1)
        
    logger.info(f"Loaded {len(leads)} leads for campaign.")
    
    sender_name = "Shivam"
    sender_email = "sriharshith0511@gmail.com"
    
    # Save original Groq API Key
    original_groq_key = settings.GROQ_API_KEY
    
    try:
        for idx, lead in enumerate(leads, 1):
            lead_name = f"{lead.get('first_name', '')} {lead.get('last_name', '')}".strip()
            logger.info(f"\n--- Testing Lead {idx}: {lead_name} ({lead.get('email')}) ---")
            
            # Formats simple placeholders
            body_formatted = _format_template(campaign["body_template"], lead, lead_name, sender_name, sender_email)
            logger.info(f"Formatted body before AI:\n{body_formatted}\n")
            
            # --- Part A: Primary LLM Path (Groq) ---
            logger.info("Executing placeholder resolution via Primary LLM (Groq)...")
            await _clear_cached_placeholders(campaign_id, lead["id"])
            
            resolved_primary = await _ai_generate_placeholders(
                body_formatted, lead, campaign, lead_name, sender_name
            )
            
            logger.info(f"Resolved body via Primary LLM:\n{resolved_primary}\n")
            
            # Verifications
            assert lead_name in resolved_primary, "Error: Investor name not found in resolved email"
            assert "{" not in resolved_primary and "}" not in resolved_primary, "Error: Curly brace placeholders remaining"
            # Verify focus area resolved (should not contain [Investor Focus Area] or [Investor Focus 1] etc.)
            assert "[investor focus" not in resolved_primary.lower(), "Error: Investor focus placeholder remaining"
            assert "[ai_value_prop]" not in resolved_primary.lower() and "{{ai_value_prop}}" not in resolved_primary.lower(), "Error: value prop placeholder remaining"
            
            # --- Part B: Fallback LLM Path (Gemini) ---
            logger.info("Corrupting Groq API key to simulate failure...")
            settings.GROQ_API_KEY = "gsk_invalid_key_for_testing_fallback"
            
            logger.info("Executing placeholder resolution via Fallback LLM (Gemini)...")
            await _clear_cached_placeholders(campaign_id, lead["id"])
            
            resolved_fallback = await _ai_generate_placeholders(
                body_formatted, lead, campaign, lead_name, sender_name
            )
            
            logger.info(f"Resolved body via Fallback LLM:\n{resolved_fallback}\n")
            
            # Verifications
            assert lead_name in resolved_fallback, "Error: Investor name not found in fallback resolved email"
            assert "{" not in resolved_fallback and "}" not in resolved_fallback, "Error: Curly brace placeholders remaining in fallback"
            assert "[investor focus" not in resolved_fallback.lower(), "Error: Investor focus placeholder remaining in fallback"
            assert "[ai_value_prop]" not in resolved_fallback.lower() and "{{ai_value_prop}}" not in resolved_fallback.lower(), "Error: value prop placeholder remaining in fallback"
            
            # Restore original key
            settings.GROQ_API_KEY = original_groq_key
            logger.info(f"Lead {idx} verified successfully on both primary and fallback LLMs!")
            
        logger.info("\n=========================================")
        logger.info("ALL TESTS COMPLETED SUCCESSFULLY! ✓")
        logger.info("1. All placeholders function correctly.")
        logger.info("2. Failover to Google Gemini fallback model works perfectly.")
        logger.info("3. Personalization and formatting are fully verified.")
        logger.info("=========================================")
        
    finally:
        # Guarantee key restoration
        settings.GROQ_API_KEY = original_groq_key

if __name__ == "__main__":
    asyncio.run(test_verification())
