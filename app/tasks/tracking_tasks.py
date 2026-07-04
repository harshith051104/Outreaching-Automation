"""
Tracking tasks - Gmail reply polling.
"""

import asyncio
import logging
from datetime import datetime, timezone
from app.config.redis_config import celery_app

from app.config.mongodb_config import get_database
from app.services.gmail_service import check_for_replies
from app.services.tracking_service import record_reply
from app.websocket.connection_manager import manager

logger = logging.getLogger(__name__)


async def poll_gmail_replies() -> dict:
    """Poll Gmail for new replies and process them."""
    db = await get_database()

    cursor = db.campaigns.find({"status": "active", "gmail_account_id": {"$ne": ""}}).limit(50)
    campaigns = await cursor.to_list(length=50)

    if not campaigns:
        return {"status": "ok", "campaigns_polled": 0}

    total_replies = 0
    for campaign in campaigns:
        try:
            count = await _poll_campaign_replies(campaign)
            total_replies += count
        except Exception as exc:
            logger.exception("Failed to poll replies for campaign %s: %s", campaign["id"], exc)

    return {
        "status": "processed",
        "campaigns_polled": len(campaigns),
        "total_replies_found": total_replies,
    }


async def _poll_campaign_replies(campaign: dict) -> int:
    """Poll a single campaign's Gmail threads for replies."""
    db = await get_database()
    gmail_account_id = campaign["gmail_account_id"]

    cursor = db.emails.find(
        {"campaign_id": campaign["id"], "status": "sent", "gmail_thread_id": {"$ne": None}},
        {"gmail_thread_id": 1},
    )
    emails = await cursor.to_list(length=500)

    if not emails:
        return 0

    thread_ids = list({e.get("gmail_thread_id") for e in emails if e.get("gmail_thread_id")})
    replies = await check_for_replies(gmail_account_id, thread_ids)

    for reply in replies:
        original_email = await db.emails.find_one({
            "campaign_id": campaign["id"],
            "gmail_thread_id": reply.get("thread_id"),
        })
        if not original_email:
            continue

        tracking_id = original_email.get("tracking_id", "")

        await record_reply(
            tracking_id,
            {
                "gmail_message_id": reply.get("gmail_message_id"),
                "from": reply.get("from", ""),
                "subject": reply.get("subject", ""),
                "snippet": reply.get("snippet", ""),
            },
            gmail_thread_id=reply.get("thread_id", ""),
        )

        try:
            campaign_owner = campaign.get("user_id")
            if campaign_owner:
                await manager.broadcast_reply(campaign_owner, {
                    "reply_id": tracking_id,
                    "campaign_id": campaign["id"],
                    "from_email": reply.get("from", ""),
                    "subject": reply.get("subject", ""),
                    "snippet": reply.get("snippet", ""),
                    "received_at": datetime.now(timezone.utc).isoformat(),
                })
        except Exception:
            pass

        try:
            from app.agents.reply_classification_agent import classify_reply
            lead = await db.leads.find_one({"id": original_email.get("lead_id")})
            classification = await asyncio.to_thread(
                classify_reply,
                reply_text=reply.get("snippet", ""),
                original_email=original_email.get("subject", ""),
                lead_context={
                    "name": f"{lead.get('first_name', '')} {lead.get('last_name', '')}".strip() if lead else "",
                    "company": lead.get("company", "") if lead else "",
                    "role": lead.get("title", "") if lead else "",
                    "lead_score": lead.get("engagement_score", 50) if lead else 50,
                },
                user_id=campaign_owner,
            )

            await db.replies.update_one(
                {"gmail_message_id": reply.get("gmail_message_id")},
                {"$set": {
                    "classification": classification.get("classification"),
                    "sentiment": classification.get("sentiment"),
                    "confidence_score": classification.get("confidence_score", 0),
                    "lead_score_delta": classification.get("lead_score_delta", 0),
                    "classification_reasoning": classification.get("reasoning", ""),
                }},
            )
        except Exception as exc:
            logger.exception("Reply classification failed: %s", exc)

    return len(replies)


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