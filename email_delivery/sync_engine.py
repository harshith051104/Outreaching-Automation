"""
Gmail reply sync engine — polls Gmail threads for new replies.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict

from app.config.mongodb_config import get_database
from email_delivery.tracking.reply_detector import record_reply

logger = logging.getLogger(__name__)


async def poll_gmail_replies() -> Dict[str, Any]:
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


async def _poll_campaign_replies(campaign: Dict[str, Any]) -> int:
    from app.services.gmail_service import check_for_replies

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
            from app.websocket.connection_manager import manager
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
            campaign_owner = campaign.get("user_id")
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
