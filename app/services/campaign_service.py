"""
Campaign service layer.

Combines v1 and v2 campaign features:
- Multi-step email sequences with A/B testing variants
- Campaign scheduling with time windows
- Daily sending limits and throttling
- Stop-on-reply handling
- Email account rotation
- Stats and analytics with step-level breakdown
"""

import asyncio
import logging
from datetime import datetime, timezone, date, time
from typing import Any, Optional, Dict, List

from fastapi import HTTPException, status

from app.config.mongodb_config import get_database
from app.utils.id_generator import generate_id

logger = logging.getLogger(__name__)

_background_tasks: set = set()


# ── CRUD Operations ────────────────────────────────────────────────────────


async def create_campaign(user_id: str, data: Any) -> Dict:
    """Create a new campaign supporting both simple and advanced v2 schemas."""
    db = await get_database()
    now = datetime.now(timezone.utc)

    def get_val(key, default=None):
        if isinstance(data, dict):
            return data.get(key, default)
        return getattr(data, key, default)

    # 1. Determine if it's a v2 campaign (possesses sequences, schedule, etc.)
    has_sequences = hasattr(data, "sequences") or (isinstance(data, dict) and "sequences" in data)

    if has_sequences:
        # Advanced v2 schema
        sequences = get_val("sequences")
        campaign_schedule = get_val("campaign_schedule")
        settings = get_val("settings")
        email_list = get_val("email_list", [])
        email_tag_list = get_val("email_tag_list", [])
        is_evergreen = get_val("is_evergreen", False)

        campaign_doc = {
            "id": generate_id(),
            "user_id": user_id,
            "name": (get_val("name") or "").strip(),
            "description": get_val("description", ""),
            "status": "draft",
            
            # Sequences
            "sequences": [seq.model_dump() if hasattr(seq, "model_dump") else seq for seq in sequences] if sequences else [],
            
            # Schedule
            "campaign_schedule": campaign_schedule.model_dump() if hasattr(campaign_schedule, "model_dump") else campaign_schedule,
            
            # Email accounts
            "email_list": email_list,
            "email_tag_list": email_tag_list,
            
            # Settings
            "settings": settings.model_dump() if hasattr(settings, "model_dump") else settings,
            "is_evergreen": is_evergreen,
            
            # Analytics
            "total_leads": 0,
            "emails_sent": 0,
            "open_count": 0,
            "click_count": 0,
            "reply_count": 0,
            "bounce_count": 0,
            "unsubscribe_count": 0,
            
            # Timestamps
            "created_at": now,
            "updated_at": now,
            "started_at": None,
        }
    else:
        # Simple v1 schema fallback
        campaign_doc = {
            "id": generate_id(),
            "user_id": user_id,
            "name": (get_val("name") or "").strip(),
            "description": get_val("description", ""),
            "gmail_account_id": get_val("gmail_account_id", ""),
            "subject_template": get_val("subject_template", ""),
            "body_template": get_val("body_template", ""),
            "followup_enabled": get_val("followup_enabled", False),
            "followup_stages": get_val("followup_stages", 3),
            "followup_delay_days": get_val("followup_delay_days", 3),
            "daily_send_limit": get_val("daily_send_limit", 50),
            "status": "draft",
            "total_leads": 0,
            "emails_sent": 0,
            "sequence_steps": get_val("sequence_steps") or [],
            "created_at": now,
            "updated_at": now,
        }

    await db.campaigns.insert_one(campaign_doc)
    campaign_doc.pop("_id", None)
    return campaign_doc


async def get_campaigns(
    user_id: str,
    skip: int = 0,
    limit: int = 20,
    status_filter: Optional[str] = None,
) -> List[Dict]:
    """List active/draft campaigns for a user with optional status filter."""
    db = await get_database()
    query: dict[str, Any] = {"user_id": user_id, "status": {"$ne": "deleted"}}
    if status_filter:
        query["status"] = status_filter

    cursor = (
        db.campaigns.find(query, {"_id": 0})
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
    )
    return await cursor.to_list(length=limit)


async def get_campaign(campaign_id: str, user_id: str) -> Dict:
    """Get a single campaign by ID, verifying ownership."""
    db = await get_database()
    campaign = await db.campaigns.find_one({"id": campaign_id, "user_id": user_id}, {"_id": 0})
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found.")
    return campaign


async def update_campaign(campaign_id: str, user_id: str, data: Any) -> Dict:
    """Update campaign fields (supporting both simple and advanced nested structures)."""
    db = await get_database()

    update_fields = data.model_dump(exclude_unset=True) if hasattr(data, 'model_dump') else {k: v for k, v in data.items() if v is not None}
    if not update_fields:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update.")

    # Serialize nested models if they are present in v2 schemas
    if "sequences" in update_fields and update_fields["sequences"] is not None:
        update_fields["sequences"] = [
            seq.model_dump() if hasattr(seq, "model_dump") else seq
            for seq in update_fields["sequences"]
        ]
    if "campaign_schedule" in update_fields and update_fields["campaign_schedule"] is not None:
        sched = update_fields["campaign_schedule"]
        update_fields["campaign_schedule"] = (
            sched.model_dump() if hasattr(sched, "model_dump") else sched
        )
    if "settings" in update_fields and update_fields["settings"] is not None:
        sett = update_fields["settings"]
        update_fields["settings"] = (
            sett.model_dump() if hasattr(sett, "model_dump") else sett
        )

    update_fields["updated_at"] = datetime.now(timezone.utc)

    result = await db.campaigns.update_one(
        {"id": campaign_id, "user_id": user_id},
        {"$set": update_fields},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found.")

    return await get_campaign(campaign_id, user_id)


async def delete_campaign(campaign_id: str, user_id: str) -> bool:
    """Soft-delete a campaign."""
    db = await get_database()
    result = await db.campaigns.update_one(
        {"id": campaign_id, "user_id": user_id},
        {"$set": {"status": "deleted", "updated_at": datetime.now(timezone.utc)}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found.")
    return True


# ── Campaign Control ───────────────────────────────────────────────────────


async def start_campaign(campaign_id: str, user_id: str) -> Dict:
    """Start an active campaign."""
    campaign = await get_campaign(campaign_id, user_id)

    if campaign["status"] == "active":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Campaign is already active.")

    if campaign["status"] == "completed":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Campaign has already been completed.")

    db = await get_database()
    await db.campaigns.update_one(
        {"id": campaign_id},
        {"$set": {"status": "active", "started_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc)}},
    )

    try:
        from app.tasks.campaign_tasks import _execute_campaign_async

        async def _run_campaign():
            try:
                result = await _execute_campaign_async(campaign_id)
                logger.info("Campaign %s execution result: %s", campaign_id, result)
            except Exception as exc:
                logger.exception("Campaign %s background execution failed: %s", campaign_id, exc)

        task = asyncio.create_task(_run_campaign())
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
    except Exception as exc:
        logger.warning("Could not start campaign task: %s", exc)

    return await get_campaign(campaign_id, user_id)


async def pause_campaign(campaign_id: str, user_id: str) -> Dict:
    """Pause an active campaign."""
    campaign = await get_campaign(campaign_id, user_id)

    if campaign["status"] != "active":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only active campaigns can be paused.")

    db = await get_database()
    await db.campaigns.update_one(
        {"id": campaign_id},
        {"$set": {"status": "paused", "updated_at": datetime.now(timezone.utc)}},
    )

    return await get_campaign(campaign_id, user_id)


async def stop_campaign(campaign_id: str, user_id: str) -> Dict:
    """Stop a campaign (alias for pause)."""
    return await pause_campaign(campaign_id, user_id)


# ── Duplicate Campaign ─────────────────────────────────────────────────────


async def duplicate_campaign(campaign_id: str, user_id: str) -> Dict:
    """Create a copy of an existing campaign."""
    original = await get_campaign(campaign_id, user_id)

    now = datetime.now(timezone.utc)
    campaign_doc = {
        "id": generate_id(),
        "user_id": user_id,
        "name": f"{original['name']} (Copy)",
        "description": original.get("description", ""),
        "status": "draft",
        "created_at": now,
        "updated_at": now,
        "started_at": None,
    }

    # copy v2 attributes if present
    for k in ["sequences", "campaign_schedule", "email_list", "email_tag_list", "settings", "is_evergreen"]:
        if k in original:
            campaign_doc[k] = original[k]

    # copy v1 attributes if present
    for k in ["gmail_account_id", "subject_template", "body_template", "followup_enabled", "followup_stages", "followup_delay_days", "daily_send_limit"]:
        if k in original:
            campaign_doc[k] = original[k]

    db = await get_database()
    await db.campaigns.insert_one(campaign_doc)
    campaign_doc.pop("_id", None)
    return campaign_doc


# ── Stats & Analytics ──────────────────────────────────────────────────────


async def get_campaign_stats(campaign_id: str) -> Dict:
    """Aggregate real-time simple stats for a campaign."""
    db = await get_database()

    total_leads = await db.leads.count_documents({"campaign_id": campaign_id})
    total_emails = await db.emails.count_documents({"campaign_id": campaign_id})
    emails_sent = await db.emails.count_documents({"campaign_id": campaign_id, "status": "sent"})
    emails_failed = await db.emails.count_documents({"campaign_id": campaign_id, "status": "failed"})

    opens = await db.tracking_events.count_documents({"campaign_id": campaign_id, "event_type": "open"})
    clicks = await db.tracking_events.count_documents({"campaign_id": campaign_id, "event_type": "click"})
    replies = await db.tracking_events.count_documents({"campaign_id": campaign_id, "event_type": "reply"})

    unique_opens_pipeline = [
        {"$match": {"campaign_id": campaign_id, "event_type": "open"}},
        {"$group": {"_id": "$email_id"}},
        {"$count": "total"},
    ]
    unique_opens_result = await db.tracking_events.aggregate(unique_opens_pipeline).to_list(length=1)
    unique_opens = unique_opens_result[0]["total"] if unique_opens_result else 0

    open_rate = (unique_opens / emails_sent * 100) if emails_sent > 0 else 0.0
    click_rate = (clicks / emails_sent * 100) if emails_sent > 0 else 0.0
    reply_rate = (replies / emails_sent * 100) if emails_sent > 0 else 0.0

    return {
        "campaign_id": campaign_id,
        "total_leads": total_leads,
        "total_emails": total_emails,
        "emails_sent": emails_sent,
        "emails_failed": emails_failed,
        "total_opens": opens,
        "unique_opens": unique_opens,
        "total_clicks": clicks,
        "total_replies": replies,
        "open_rate": round(open_rate, 2),
        "click_rate": round(click_rate, 2),
        "reply_rate": round(reply_rate, 2),
    }


async def get_campaign_analytics(campaign_id: str, user_id: str) -> Dict:
    """Get comprehensive analytics for a campaign (v2 analytics support)."""
    db = await get_database()

    # Verify ownership
    campaign = await get_campaign(campaign_id, user_id)

    total_leads = await db.leads.count_documents({"campaign_id": campaign_id})
    emails_sent = await db.emails.count_documents({"campaign_id": campaign_id, "status": "sent"})
    emails_delivered = await db.emails.count_documents(
        {"campaign_id": campaign_id, "status": {"$in": ["sent", "delivered"]}}
    )

    opens = await db.tracking_events.count_documents({"campaign_id": campaign_id, "event_type": "open"})
    clicks = await db.tracking_events.count_documents({"campaign_id": campaign_id, "event_type": "click"})
    replies = await db.tracking_events.count_documents({"campaign_id": campaign_id, "event_type": "reply"})
    bounces = await db.emails.count_documents({"campaign_id": campaign_id, "status": "bounced"})
    unsubscribes = await db.tracking_events.count_documents({"campaign_id": campaign_id, "event_type": "unsubscribe"})

    # Unique opens
    unique_opens_pipeline = [
        {"$match": {"campaign_id": campaign_id, "event_type": "open"}},
        {"$group": {"_id": "$email_id"}},
        {"$count": "total"},
    ]
    unique_opens_result = await db.tracking_events.aggregate(unique_opens_pipeline).to_list(1)
    unique_opens = unique_opens_result[0]["total"] if unique_opens_result else 0

    # Unique clicks
    unique_clicks_pipeline = [
        {"$match": {"campaign_id": campaign_id, "event_type": "click"}},
        {"$group": {"_id": "$email_id"}},
        {"$count": "total"},
    ]
    unique_clicks_result = await db.tracking_events.aggregate(unique_clicks_pipeline).to_list(1)
    unique_clicks = unique_clicks_result[0]["total"] if unique_clicks_result else 0

    def safe_rate(num, den):
        return round((num / den * 100), 2) if den > 0 else 0.0

    delivery_rate = safe_rate(emails_delivered, emails_sent)
    open_rate = safe_rate(unique_opens, emails_sent)
    click_rate = safe_rate(unique_clicks, emails_sent)
    reply_rate = safe_rate(replies, emails_sent)
    bounce_rate = safe_rate(bounces, emails_sent)
    unsubscribe_rate = safe_rate(unsubscribes, emails_sent)
    click_to_open_rate = safe_rate(unique_clicks, unique_opens)

    health_issues = []
    if bounce_rate > 5:
        health_issues.append("High bounce rate - clean your email list")
    if unsubscribe_rate > 1:
        health_issues.append("High unsubscribe rate - review content relevance")
    if open_rate < 10:
        health_issues.append("Very low open rate - improve subject lines")
    if click_rate < 1 and open_rate > 15:
        health_issues.append("Opens but no clicks - improve email body and CTA")
    if reply_rate < 0.5 and open_rate > 20:
        health_issues.append("Good opens but low replies - strengthen call to action")

    health_status = (
        "healthy" if not health_issues
        else "needs_attention" if len(health_issues) <= 2
        else "critical"
    )

    step_analytics = await _get_step_analytics(campaign_id, campaign)
    daily_analytics = await _get_daily_analytics(campaign_id)

    return {
        "campaign_id": campaign_id,
        "campaign_name": campaign["name"],
        "total_leads": total_leads,
        "emails_sent": emails_sent,
        "emails_delivered": emails_delivered,
        "emails_opened": opens,
        "unique_opens": unique_opens,
        "emails_clicked": clicks,
        "unique_clicks": unique_clicks,
        "emails_replied": replies,
        "emails_bounced": bounces,
        "unsubscribes": unsubscribes,
        "delivery_rate": delivery_rate,
        "open_rate": open_rate,
        "click_rate": click_rate,
        "reply_rate": reply_rate,
        "bounce_rate": bounce_rate,
        "unsubscribe_rate": unsubscribe_rate,
        "click_to_open_rate": click_to_open_rate,
        "step_analytics": step_analytics,
        "daily_analytics": daily_analytics,
        "health_status": health_status,
        "health_issues": health_issues,
    }


async def _get_step_analytics(campaign_id: str, campaign: Dict) -> List[Dict]:
    """Get analytics broken down by sequence step."""
    db = await get_database()
    sequences = campaign.get("sequences", [])
    if not sequences:
        return []

    steps = sequences[0].get("steps", []) if sequences else []
    step_results = []

    for i, step in enumerate(steps):
        step_num = i + 1
        sent = await db.emails.count_documents(
            {"campaign_id": campaign_id, "step": step_num, "status": "sent"}
        )
        opens = await db.tracking_events.count_documents(
            {"campaign_id": campaign_id, "step": step_num, "event_type": "open"}
        )
        clicks = await db.tracking_events.count_documents(
            {"campaign_id": campaign_id, "step": step_num, "event_type": "click"}
        )
        replies = await db.tracking_events.count_documents(
            {"campaign_id": campaign_id, "step": step_num, "event_type": "reply"}
        )

        step_results.append({
            "step": step_num,
            "delay": step.get("delay", 0),
            "delay_unit": step.get("delay_unit", "days"),
            "variants": len(step.get("variants", [])),
            "emails_sent": sent,
            "opens": opens,
            "clicks": clicks,
            "replies": replies,
            "open_rate": round(opens / sent * 100, 2) if sent > 0 else 0.0,
            "click_rate": round(clicks / sent * 100, 2) if sent > 0 else 0.0,
            "reply_rate": round(replies / sent * 100, 2) if sent > 0 else 0.0,
        })

    return step_results


async def _get_daily_analytics(campaign_id: str) -> List[Dict]:
    """Get daily analytics breakdown."""
    db = await get_database()

    pipeline = [
        {"$match": {"campaign_id": campaign_id}},
        {
            "$group": {
                "_id": {
                    "date": {"$dateToString": {"format": "%Y-%m-%d", "date": "$timestamp"}},
                    "event_type": "$event_type",
                },
                "count": {"$sum": 1},
            }
        },
        {"$sort": {"_id.date": 1}},
    ]

    results = await db.tracking_events.aggregate(pipeline).to_list(length=500)

    daily: dict[str, dict] = {}
    for r in results:
        date_str = r["_id"]["date"]
        event_type = r["_id"]["event_type"]
        if date_str not in daily:
            daily[date_str] = {"date": date_str, "opens": 0, "clicks": 0, "replies": 0, "bounces": 0}
        if event_type == "open":
            daily[date_str]["opens"] = r["count"]
        elif event_type == "click":
            daily[date_str]["clicks"] = r["count"]
        elif event_type == "reply":
            daily[date_str]["replies"] = r["count"]

    return list(daily.values())


# ── Scheduling checks ───────────────────────────────────────────────────────


def is_campaign_in_schedule(campaign: Dict) -> bool:
    """Check if the current time falls within the campaign's sending schedule."""
    schedule = campaign.get("campaign_schedule", {})
    schedules = schedule.get("schedules", [])

    if not schedules:
        return True  # No schedule = always send

    now = datetime.now(timezone.utc)
    current_day_instantly = str((now.weekday() + 1) % 7)
    current_time = now.strftime("%H:%M")

    for sched in schedules:
        days = sched.get("days", {})
        if not days.get(current_day_instantly, False):
            continue

        timing = sched.get("timing", {})
        from_time = timing.get("from", "00:00")
        to_time = timing.get("to", "23:59")

        if from_time <= current_time <= to_time:
            return True

    return False