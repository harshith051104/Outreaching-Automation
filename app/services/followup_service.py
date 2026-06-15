"""
Follow-up service layer.

Manages scheduled follow-up emails: creation, execution,
cancellation, and querying pending follow-ups.
"""

from datetime import datetime, timezone

from fastapi import HTTPException, status

from app.config.mongodb_config import get_database
from app.utils.id_generator import generate_id, generate_tracking_id


async def create_followup(
    email_id: str,
    campaign_id: str,
    lead_id: str,
    user_id: str,
    sequence_number: int,
    scheduled_at: datetime,
) -> dict:
    """
    Schedule a follow-up email for a lead.

    The follow-up remains 'pending' until executed or cancelled.
    """
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


async def get_pending_followups(user_id: str | None = None) -> list:
    """
    Retrieve pending follow-ups.

    If user_id is provided, filter to that user only.
    Otherwise return all pending follow-ups (used by the Celery task).
    """
    db = await get_database()
    query: dict = {"status": "pending"}
    if user_id:
        query["user_id"] = user_id

    cursor = (
        db.followup_tasks.find(query, {"_id": 0})
        .sort("scheduled_at", 1)
        .limit(200)
    )
    return await cursor.to_list(length=200)


async def get_followups(
    user_id: str,
    campaign_id: str | None = None,
    lead_id: str | None = None,
    status: str | None = None,
) -> list:
    """Retrieve all follow-up tasks with optional filters."""
    db = await get_database()
    query: dict = {"user_id": user_id}
    if campaign_id:
        query["campaign_id"] = campaign_id
    if lead_id:
        query["lead_id"] = lead_id
    if status:
        query["status"] = status

    cursor = (
        db.followup_tasks.find(query, {"_id": 0})
        .sort("scheduled_at", 1)
        .limit(500)
    )
    return await cursor.to_list(length=500)



async def execute_followup(followup_id: str) -> dict:
    """
    Execute a pending follow-up: generate follow-up content and send.

    Loads the original email context, generates a follow-up body,
    creates a new email, and sends it.
    """
    db = await get_database()

    followup = await db.followup_tasks.find_one({"id": followup_id})
    if not followup:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Follow-up task not found.",
        )

    if followup["status"] != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Follow-up is already {followup['status']}.",
        )

    original_email = await db.emails.find_one({"id": followup["email_id"]})
    if not original_email:
        await _mark_followup(followup_id, "failed")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Original email not found.",
        )

    lead = await db.leads.find_one({"id": followup["lead_id"]})
    lead_name = ""
    if lead:
        lead_name = f'{lead.get("first_name", "")} {lead.get("last_name", "")}'.strip()

    seq = followup["sequence_number"]
    subject = f"Re: {original_email['subject']}"
    body_html = (
        f"<p>Hi {lead_name or 'there'},</p>"
        f"<p>I wanted to follow up on my previous email regarding "
        f"<strong>{original_email['subject']}</strong>.</p>"
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

    new_email = await create_email(
        user_id=followup["user_id"], data=email_data, tracking_id=tracking_id
    )

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
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to send follow-up: {exc}",
        )

    followup_doc = await db.followup_tasks.find_one(
        {"id": followup_id}, {"_id": 0}
    )
    return followup_doc


async def cancel_followup(followup_id: str) -> dict:
    """Cancel a pending follow-up task."""
    db = await get_database()
    result = await db.followup_tasks.find_one_and_update(
        {"id": followup_id, "status": "pending"},
        {
            "$set": {
                "status": "cancelled",
                "updated_at": datetime.now(timezone.utc),
            }
        },
        return_document=True,
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pending follow-up not found.",
        )
    result.pop("_id", None)
    return result


async def cancel_lead_followups(lead_id: str) -> None:
    """
    Cancel all pending follow-ups for a lead.

    Typically called when a lead replies, making further follow-ups unnecessary.
    """
    db = await get_database()
    await db.followup_tasks.update_many(
        {"lead_id": lead_id, "status": "pending"},
        {
            "$set": {
                "status": "cancelled",
                "updated_at": datetime.now(timezone.utc),
            }
        },
    )


async def _mark_followup(
    followup_id: str, new_status: str, result_email_id: str | None = None
) -> None:
    """Update a follow-up task's status."""
    db = await get_database()
    update: dict = {
        "status": new_status,
        "updated_at": datetime.now(timezone.utc),
    }
    if new_status == "executed":
        update["executed_at"] = datetime.now(timezone.utc)
    if result_email_id:
        update["result_email_id"] = result_email_id

    await db.followup_tasks.update_one({"id": followup_id}, {"$set": update})