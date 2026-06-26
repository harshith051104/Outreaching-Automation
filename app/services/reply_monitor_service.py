"""
Reply Monitor Service.

Provides real-time reply monitoring, draft response generation,
and user-approval workflow for incoming email replies.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from app.config.mongodb_config import get_database
from app.utils.id_generator import generate_id

logger = logging.getLogger(__name__)


async def get_pending_replies(user_id: str, limit: int = 50) -> list:
    """
    Get all unprocessed replies for a user's campaigns.

    Returns replies that haven't been responded to yet, newest first.
    """
    db = await get_database()

    campaign_cursor = db.campaigns.find({"user_id": user_id}, {"id": 1})
    campaigns = await campaign_cursor.to_list(length=200)
    campaign_ids = [c["id"] for c in campaigns]

    if not campaign_ids:
        return []

    cursor = db.replies.find(
        {
            "campaign_id": {"$in": campaign_ids},
            "draft_response.status": {"$ne": "sent"},
        },
        {"_id": 0},
    ).sort("received_at", -1).limit(limit)

    return await cursor.to_list(length=limit)


async def get_reply_details(reply_id: str) -> Optional[dict]:
    """Get full details for a single reply."""
    db = await get_database()
    reply = await db.replies.find_one({"id": reply_id}, {"_id": 0})
    if not reply:
        return None

    if reply.get("lead_id"):
        lead = await db.leads.find_one({"id": reply["lead_id"]}, {"_id": 0})
        reply["lead"] = lead

    if reply.get("campaign_id"):
        campaign = await db.campaigns.find_one({"id": reply["campaign_id"]}, {"_id": 0})
        reply["campaign"] = campaign

    if reply.get("email_id"):
        email = await db.emails.find_one({"id": reply["email_id"]}, {"_id": 0})
        reply["original_email"] = email

    return reply


async def generate_draft_response(reply_id: str, gmail_account_id: Optional[str] = None) -> dict:
    """
    Generate a draft response for a reply using the AI followup agent.

    Stores the draft in the reply document and returns it.
    """
    db = await get_database()
    reply = await db.replies.find_one({"id": reply_id})
    if not reply:
        raise ValueError(f"Reply {reply_id} not found")

    lead = None
    if reply.get("lead_id"):
        lead = await db.leads.find_one({"id": reply["lead_id"]})

    original_email = None
    if reply.get("email_id"):
        original_email = await db.emails.find_one({"id": reply["email_id"]})

    # Resolve sender name and update chosen gmail_account_id
    if not gmail_account_id:
        gmail_account_id = reply.get("gmail_account_id")

    sender_name = ""
    if gmail_account_id:
        gmail_account = await db.gmail_accounts.find_one({"id": gmail_account_id})
        if gmail_account:
            await db.replies.update_one({"id": reply_id}, {"$set": {"gmail_account_id": gmail_account_id}})
            user = await db.users.find_one({"id": gmail_account["user_id"]})
            user_name = user.get("name", "") if user else ""
            sender_name = gmail_account.get("name", user_name)

    if not sender_name:
        campaign = None
        if reply.get("campaign_id"):
            campaign = await db.campaigns.find_one({"id": reply["campaign_id"]})

        if campaign:
            user = await db.users.find_one({"id": campaign["user_id"]})
            user_name = user.get("name", "") if user else ""
            
            campaign_gmail_id = campaign.get("gmail_account_id", "")
            if campaign_gmail_id:
                gmail_account = await db.gmail_accounts.find_one({"id": campaign_gmail_id})
                sender_name = gmail_account.get("name", user_name) if gmail_account else user_name
                # Persist the campaign's gmail_account_id to the reply document
                await db.replies.update_one({"id": reply_id}, {"$set": {"gmail_account_id": campaign_gmail_id}})
            else:
                sender_name = user_name

    lead_context = {
        "name": lead.get("name", "") if lead else "",
        "company": lead.get("company", "") if lead else "",
        "role": lead.get("role", "") if lead else "",
        "lead_score": lead.get("engagement_score", 50) if lead else 50,
        "sender_name": sender_name,
    }

    classification = None
    try:
        from app.agents.reply_classification_agent import classify_reply
        classification = await asyncio.to_thread(
            classify_reply,
            reply_text=reply.get("snippet", reply.get("body", "")),
            original_email=original_email.get("subject", "") if original_email else "",
            lead_context=lead_context,
        )
    except Exception as exc:
        logger.warning("Reply classification failed: %s", exc)

    draft = None
    try:
        from app.agents.followup_agent import generate_followup
        if original_email:
            original_email_data = {
                "subject": original_email.get("subject", ""),
                "body_text": original_email.get("body_text") or original_email.get("body_html", "") or original_email.get("snippet", ""),
            }
        else:
            original_email_data = {
                "subject": reply.get("subject", ""),
                "body_text": reply.get("body", "") or reply.get("snippet", ""),
            }
            logger.info(f"No original email found for reply {reply_id}, using reply context for draft generation")

        draft = await asyncio.to_thread(
            generate_followup,
            original_email=original_email_data,
            lead_data=lead_context,
            sequence_number=1,
            engagement_data={
                "replied": True,
                "reply_snippet": reply.get("snippet", ""),
                "classification": classification.get("classification") if classification else "unknown",
            },
        )
    except Exception as exc:
        import traceback
        try:
            with open(r"c:\Users\sriha\My work\Outreach\ai_outreach_v2_md_agents\real_draft_error.txt", "w", encoding="utf-8") as f:
                traceback.print_exc(file=f)
        except Exception:
            pass
        logger.exception("Draft generation failed: %s", exc)
        draft = {
            "subject": f"Re: {reply.get('subject', '')}",
            "body_text": "",
            "body_html": "",
        }

    now = datetime.now(timezone.utc)
    draft_doc = {
        "subject": draft.get("subject", f"Re: {reply.get('subject', '')}"),
        "body_text": draft.get("body_text", ""),
        "body_html": draft.get("body_html", ""),
        "generated_at": now,
        "status": "pending",
        "classification": classification,
    }

    await db.replies.update_one(
        {"id": reply_id},
        {"$set": {
            "draft_response": draft_doc,
            "confidence_score": classification.get("confidence_score") if classification else None,
            "classification_sentiment": classification.get("sentiment") if classification else None,
            "classification_reasoning": classification.get("reasoning") if classification else None,
        }},
    )

    # Notify campaign owner that a draft reply is ready for review
    try:
        campaign = await db.campaigns.find_one({"id": reply.get("campaign_id", "")}, {"user_id": 1, "name": 1})
        if campaign and campaign.get("user_id"):
            from app.services.notification_service import notify
            lead_from = reply.get("from_email", "a lead")
            await notify(
                user_id=campaign["user_id"],
                type="reply_draft_generated",
                title="Reply Draft Ready",
                message=f"AI generated a draft reply to {lead_from} for campaign '{campaign.get('name', '')}'.",
                reference_id=reply_id,
                reference_type="reply",
            )
    except Exception:
        pass

    return {
        "reply_id": reply_id,
        "draft": draft_doc,
        "classification": classification,
    }


async def approve_draft(reply_id: str, user_id: str) -> dict:
    """
    Approve and send a draft response.

    Updates the draft status and sends the email via Gmail.
    """
    db = await get_database()
    reply = await db.replies.find_one({"id": reply_id})
    if not reply:
        raise ValueError(f"Reply {reply_id} not found")

    draft = reply.get("draft_response")
    if not draft:
        raise ValueError(f"No draft response found for reply {reply_id}")

    if draft.get("status") == "sent":
        raise ValueError("Draft has already been sent")

    gmail_account_id = reply.get("gmail_account_id")
    if not gmail_account_id:
        campaign = None
        if reply.get("campaign_id"):
            campaign = await db.campaigns.find_one({"id": reply["campaign_id"]})

        gmail_account_id = campaign.get("gmail_account_id", "") if campaign else ""

    if not gmail_account_id:
        raise ValueError("No Gmail account configured for this campaign")

    # Get thread_id - from reply document first, fallback to original email's thread
    gmail_thread_id = reply.get("gmail_thread_id", "")
    # The gmail_message_id of the reply we received — used as In-Reply-To
    gmail_message_id = reply.get("gmail_message_id", "")
    if not gmail_thread_id and reply.get("email_id"):
        original_email = await db.emails.find_one({"id": reply["email_id"]})
        if original_email:
            gmail_thread_id = original_email.get("gmail_thread_id", "")

    lead_email = reply.get("from_email", "")
    if not lead_email and reply.get("lead_id"):
        lead = await db.leads.find_one({"id": reply["lead_id"]})
        if lead:
            lead_email = lead.get("email", "")

    if not lead_email:
        raise ValueError("No recipient email found")

    try:
        from app.services.gmail_service import send_email

        body_html = draft.get("body_html", "")
        body_text = draft.get("body_text", "")
        if not body_html and body_text:
            body_html = f"<p>{body_text.replace(chr(10), '<br>')}</p>"
        elif not body_html:
            body_html = "<p>No content</p>"

        result = await send_email(
            gmail_account_id=gmail_account_id,
            to=lead_email,
            subject=draft.get("subject", ""),
            body_html=body_html,
            thread_id=gmail_thread_id,
            # RFC 2822 threading: continue in the same Gmail thread
            in_reply_to=gmail_message_id if gmail_message_id else None,
            references=gmail_message_id if gmail_message_id else None,
        )

        now = datetime.now(timezone.utc)
        await db.replies.update_one(
            {"id": reply_id},
            {"$set": {
                "draft_response.status": "sent",
                "draft_response.sent_at": now,
                "draft_response.sent_by": user_id,
            }},
        )

        return {
            "status": "sent",
            "reply_id": reply_id,
            "gmail_message_id": result.get("gmail_message_id"),
        }

    except Exception as exc:
        logger.exception("Failed to send draft response")
        await db.replies.update_one(
            {"id": reply_id},
            {"$set": {"draft_response.status": "failed", "draft_response.error": str(exc)}},
        )
        raise


async def reject_draft(reply_id: str, reason: str = "") -> dict:
    """Reject a draft response without sending."""
    db = await get_database()
    now = datetime.now(timezone.utc)

    await db.replies.update_one(
        {"id": reply_id},
        {"$set": {
            "draft_response.status": "rejected",
            "draft_response.rejected_at": now,
            "draft_response.rejection_reason": reason,
        }},
    )

    return {"status": "rejected", "reply_id": reply_id}


async def get_monitor_stats(user_id: str) -> dict:
    """Get summary stats for the reply monitor dashboard."""
    db = await get_database()

    campaign_cursor = db.campaigns.find({"user_id": user_id}, {"id": 1})
    campaigns = await campaign_cursor.to_list(length=200)
    campaign_ids = [c["id"] for c in campaigns]

    if not campaign_ids:
        return {
            "total_replies": 0,
            "pending_drafts": 0,
            "sent_responses": 0,
            "classification_breakdown": {},
        }

    total_replies = await db.replies.count_documents(
        {"campaign_id": {"$in": campaign_ids}}
    )

    pending_drafts = await db.replies.count_documents(
        {
            "campaign_id": {"$in": campaign_ids},
            "draft_response": {"$exists": False},
        }
    )

    sent_responses = await db.replies.count_documents(
        {
            "campaign_id": {"$in": campaign_ids},
            "draft_response.status": "sent",
        }
    )

    pipeline = [
        {"$match": {"campaign_id": {"$in": campaign_ids}, "classification": {"$ne": None}}},
        {"$group": {"_id": "$classification", "count": {"$sum": 1}}},
    ]
    classification_results = await db.replies.aggregate(pipeline).to_list(length=20)
    classification_breakdown = {r["_id"]: r["count"] for r in classification_results}

    return {
        "total_replies": total_replies,
        "pending_drafts": pending_drafts,
        "sent_responses": sent_responses,
        "classification_breakdown": classification_breakdown,
    }