"""
Follow-up tasks and service.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from app.config.redis_config import celery_app

from fastapi import HTTPException, status

from app.config.mongodb_config import get_database
from app.utils.id_generator import generate_id, generate_tracking_id

logger = logging.getLogger(__name__)


async def create_followup(
    email_id: str,
    campaign_id: str,
    lead_id: str,
    user_id: str,
    sequence_number: int,
    scheduled_at: datetime,
) -> dict:
    """Schedule a follow-up email."""
    db = await get_database()
    now = datetime.now(timezone.utc)

    followup_doc = {
        "id": generate_id(),
        "email_id": email_id,
        "campaign_id": campaign_id,
        "lead_id": lead_id,
        "user_id": user_id,
        "sequence_number": sequence_number,
        "status": "pending",
        "scheduled_at": scheduled_at,
        "executed_at": None,
        "result_email_id": None,
        "created_at": now,
        "updated_at": now,
    }

    await db.followup_tasks.insert_one(followup_doc)
    followup_doc.pop("_id", None)
    return followup_doc


async def get_pending_followups(user_id: Optional[str] = None) -> list:
    """Retrieve pending follow-ups."""
    db = await get_database()
    query = {"status": "pending"}
    if user_id:
        query["user_id"] = user_id

    cursor = (
        db.followup_tasks.find(query, {"_id": 0})
        .sort("scheduled_at", 1)
        .limit(200)
    )
    return await cursor.to_list(length=200)


async def execute_followup(followup_id: str) -> dict:
    """Execute a pending follow-up."""
    db = await get_database()

    followup = await db.followup_tasks.find_one({"id": followup_id})
    if not followup:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Follow-up task not found.")

    if followup["status"] != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Follow-up is already {followup['status']}.")

    campaign = await db.campaigns.find_one({"id": followup["campaign_id"]})
    if not campaign:
        await _mark_followup(followup_id, "failed")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found.")

    if campaign.get("status") != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Campaign '{campaign.get('name', 'unknown')}' is not active (status: {campaign.get('status')}). Skipping follow-up execution."
        )

    # Count how many emails have already been sent in last hour for this Gmail account (or user)
    hour_start = datetime.now(timezone.utc) - timedelta(hours=1)
    original_email = await db.emails.find_one({"id": followup["email_id"]})
    gmail_acct_id = original_email.get("gmail_account_id") if original_email else None
    
    query = {
        "status": {"$in": ["sent", "pending", "sending", "paused"]},
        "created_at": {"$gte": hour_start}
    }
    if gmail_acct_id:
        query["gmail_account_id"] = gmail_acct_id
    elif user_id:
        query["user_id"] = user_id
    else:
        query["campaign_id"] = followup["campaign_id"]
        
    sent_today = await db.emails.count_documents(query)
    
    daily_limit = campaign.get("daily_send_limit")
    user_id = campaign.get("user_id") or followup.get("user_id")
    if user_id:
        prefs = await db.system_settings.find_one({"user_id": user_id, "type": "system_preferences"})
        if prefs and "dailyLimit" in prefs:
            daily_limit = prefs["dailyLimit"]
    if daily_limit is None:
        daily_limit = 50

    if sent_today >= daily_limit:
        next_run = datetime.now(timezone.utc) + timedelta(minutes=15)
        await db.followup_tasks.update_one(
            {"id": followup_id},
            {"$set": {
                "scheduled_at": next_run,
                "daily_limit_deferred": True,
                "updated_at": datetime.now(timezone.utc)
            }}
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Campaign '{campaign.get('name', 'unknown')}' has reached its hourly limit of {daily_limit} emails today. Deferring follow-up task to next hour."
        )

    original_email = await db.emails.find_one({"id": followup["email_id"]})
    if not original_email:
        await _mark_followup(followup_id, "failed")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Original email not found.")

    lead = await db.leads.find_one({"id": followup["lead_id"]})
    lead_name = f"{lead.get('first_name', '')} {lead.get('last_name', '')}".strip() if lead else ""

    seq = followup["sequence_number"]
    subject = f"Re: {original_email['subject']}"
    body_html = (
        f"<p>Hi {lead_name or 'there'},</p>"
        f"<p>I wanted to follow up on my previous email regarding <strong>{original_email['subject']}</strong>.</p>"
        f"<p>I understand you're busy, but I'd love to connect if you have a moment.</p>"
        f"<p>This is follow-up #{seq} in the sequence.</p>"
        f"<p>Best regards</p>"
    )

    from app.services.email_service import create_email, send_campaign_email
    from app.schemas.email import EmailCreate

    tracking_id = generate_tracking_id()

    email_data = EmailCreate(
        campaign_id=followup["campaign_id"],
        lead_id=followup["lead_id"],
        gmail_account_id=original_email["gmail_account_id"],
        to=original_email["to"],
        subject=subject,
        body_html=body_html,
        sequence_number=seq,
    )

    new_email = await create_email(user_id=followup["user_id"], data=email_data, tracking_id=tracking_id)

    if original_email.get("gmail_thread_id"):
        await db.emails.update_one(
            {"id": new_email["id"]},
            {"$set": {"gmail_thread_id": original_email["gmail_thread_id"]}},
        )

    try:
        await send_campaign_email(new_email["id"])
        await _mark_followup(followup_id, "executed", new_email["id"])
    except Exception as exc:
        await _mark_followup(followup_id, "failed")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Failed to send follow-up: {exc}")

    return await db.followup_tasks.find_one({"id": followup_id}, {"_id": 0})


async def cancel_followup(followup_id: str) -> dict:
    """Cancel a pending follow-up."""
    db = await get_database()
    result = await db.followup_tasks.find_one_and_update(
        {"id": followup_id, "status": "pending"},
        {"$set": {"status": "cancelled", "updated_at": datetime.now(timezone.utc)}},
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pending follow-up not found.")
    result.pop("_id", None)
    return result


async def cancel_lead_followups(lead_id: str) -> None:
    """Cancel all pending follow-ups for a lead."""
    db = await get_database()
    await db.followup_tasks.update_many(
        {"lead_id": lead_id, "status": "pending"},
        {"$set": {"status": "cancelled", "updated_at": datetime.now(timezone.utc)}},
    )


async def _mark_followup(followup_id: str, new_status: str, result_email_id: Optional[str] = None) -> None:
    """Update follow-up status."""
    db = await get_database()
    update = {"status": new_status, "updated_at": datetime.now(timezone.utc)}
    if new_status == "executed":
        update["executed_at"] = datetime.now(timezone.utc)
    if result_email_id:
        update["result_email_id"] = result_email_id

    await db.followup_tasks.update_one({"id": followup_id}, {"$set": update})


async def process_pending_followups() -> dict:
    """Process all due follow-ups."""
    db = await get_database()
    now = datetime.now(timezone.utc)

    pending = await db.followup_tasks.find(
        {"status": "pending", "scheduled_at": {"$lte": now}}
    ).limit(50).to_list(length=50)

    if not pending:
        return {"status": "ok", "processed": 0}

    results = []
    for followup in pending:
        try:
            await execute_followup(followup["id"])
            results.append({"followup_id": followup["id"], "status": "executed"})
        except Exception as exc:
            err_msg = str(exc).lower()
            is_transient_ai_error = any(
                kw in err_msg for kw in [
                    "rate limit", "rate_limit", "429", "limit", "api key", "apikey",
                    "placeholder", "llm", "unresolved", "groq", "nvidia", "connection", "timeout", "openai"
                ]
            )
            if is_transient_ai_error:
                from app.services.task_scheduler_service import extract_retry_delay
                delay_seconds = extract_retry_delay(str(exc), default_seconds=300)
                retry_time = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds + 5)
                logger.warning(
                    "Followup Scheduler: Task %s failed due to transient AI/rate-limit error: %s. Rescheduling in %ds (to %s) to retry.",
                    followup["id"], str(exc), delay_seconds + 5, retry_time
                )
                await db.followup_tasks.update_one(
                    {"id": followup["id"]},
                    {"$set": {
                        "scheduled_at": retry_time,
                        "error": f"Transient failure: {str(exc)}",
                        "updated_at": datetime.now(timezone.utc)
                    }}
                )
            else:
                logger.exception("Failed to execute followup task %s (permanent failure): %s", followup["id"], exc)
                await db.followup_tasks.update_one(
                    {"id": followup["id"]},
                    {"$set": {
                        "status": "failed",
                        "error": str(exc),
                        "updated_at": datetime.now(timezone.utc)
                    }}
                )
            results.append({"followup_id": followup["id"], "status": "error", "error": str(exc)})

    return {"status": "processed", "count": len(results), "results": results}


def _run_async(coro):
    """Run async coroutine synchronously inside Celery worker loop."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


@celery_app.task(name="app.tasks.followup_tasks.process_pending_followups")
def process_pending_followups_task():
    """Celery task wrapper for process_pending_followups."""
    logger.info("Celery Task: Processing pending followups...")
    result = _run_async(process_pending_followups())
    logger.info("Celery Task: Pending followups processing completed: %s", result)
    return result