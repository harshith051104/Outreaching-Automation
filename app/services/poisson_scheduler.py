"""
Poisson Scheduler — Campaign-Specific Pacing & Scheduling Engine

Calculates working hours, tz-aware windows, and daily quotas based on campaign settings.
Poisson-spaces lazy connecting, check-pending, and follow-up slots over a 24h window.
"""

from __future__ import annotations

import logging
import random
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import List, Dict, Any

from app.config.mongodb_config import get_database
from app.utils.id_generator import generate_id

logger = logging.getLogger(__name__)


def _get_working_intervals(
    start: datetime,
    end: datetime,
    start_hour: int,
    end_hour: int,
    tz_name: str
) -> List[tuple]:
    """Get list of active working intervals between start and end in target timezone."""
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("UTC")

    local_start = start.astimezone(tz)
    local_end = end.astimezone(tz)

    intervals = []
    day = local_start.date()
    last_day = local_end.date()

    while day <= last_day:
        day_active_start = datetime(
            day.year, day.month, day.day, start_hour, 0, 0, tzinfo=tz
        )
        day_active_end = datetime(
            day.year, day.month, day.day, end_hour, 0, 0, tzinfo=tz
        )
        s = max(day_active_start, local_start)
        e = min(day_active_end, local_end)
        if e > s:
            intervals.append((s, e))
        day = day + timedelta(days=1)
    return intervals


def poisson_slot_times(
    now: datetime,
    n: int,
    horizon_hours: float,
    start_hour: int,
    end_hour: int,
    tz_name: str
) -> List[datetime]:
    """Calculate n Poisson-spaced timestamps inside active hours in the horizon."""
    if n <= 0:
        return []

    end = now + timedelta(hours=horizon_hours)
    intervals = _get_working_intervals(now, end, start_hour, end_hour, tz_name)
    total_sec = sum((e - s).total_seconds() for s, e in intervals)
    if total_sec <= 0:
        return []

    # Sample uniform positions in working seconds and sort
    positions = sorted(random.uniform(0, total_sec) for _ in range(n))

    times: List[datetime] = []
    cursor_interval = 0
    cursor_offset = 0.0

    for pos in positions:
        while cursor_interval < len(intervals):
            s, e = intervals[cursor_interval]
            dur = (e - s).total_seconds()
            if pos < cursor_offset + dur:
                times.append(s + timedelta(seconds=pos - cursor_offset))
                break
            cursor_offset += dur
            cursor_interval += 1
    return times


async def plan_outreach_window(user_id: str, campaign_id: str) -> int:
    """Computes campaign-specific quotas and schedules Poisson-spaced slots over next 24 hours."""
    db = await get_database()
    
    # Strict multi-tenant verification
    campaign = await db.campaigns.find_one({"id": campaign_id, "user_id": user_id})
    if not campaign:
        logger.warning("Campaign %s not found or unauthorized for user %s", campaign_id, user_id)
        return 0

    now = datetime.now(timezone.utc)
    
    # Read campaign settings with sensible fallbacks
    tz_name = campaign.get("active_timezone") or "UTC"
    start_hour = campaign.get("active_start_hour", 9)
    end_hour = campaign.get("active_end_hour", 18)
    
    # Connection / message daily limits
    connect_limit = campaign.get("connect_daily_limit", 20)
    followup_limit = campaign.get("follow_up_daily_limit", 25)

    # Check for exhausted flags today
    session_doc = await db.linkedin_sessions.find_one({"user_id": user_id})
    connects_exhausted = False
    messages_exhausted = False
    
    today_str = now.strftime("%Y-%m-%d")
    if session_doc:
        if session_doc.get("connect_exhausted_date") == today_str:
            connects_exhausted = True
        if session_doc.get("message_exhausted_date") == today_str:
            messages_exhausted = True

    # Compute already sent count today from Action Log
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Count today's connections and messages
    sent_connects = await db.linkedin_action_logs.count_documents({
        "user_id": user_id,
        "action_type": "connect",
        "created_at": {"$gte": today_start}
    })
    
    sent_messages = await db.linkedin_action_logs.count_documents({
        "user_id": user_id,
        "action_type": "message",
        "created_at": {"$gte": today_start}
    })

    created_tasks = 0
    
    # ── Plan CONNECT slots ──
    has_pending_connect = await db.scheduled_linkedin_tasks.find_one({
        "campaign_id": campaign_id,
        "user_id": user_id,
        "task_type": "connect",
        "status": "pending"
    })
    
    if not has_pending_connect and not connects_exhausted:
        n_connect = max(0, connect_limit - sent_connects)
        if n_connect > 0:
            times = [now] + poisson_slot_times(now, n_connect - 1, 24, start_hour, end_hour, tz_name)
            for t in times:
                task_doc = {
                    "id": generate_id(),
                    "campaign_id": campaign_id,
                    "user_id": user_id,
                    "task_type": "connect",
                    "scheduled_at": t,
                    "status": "pending",
                    "created_at": now,
                    "updated_at": now
                }
                await db.scheduled_linkedin_tasks.insert_one(task_doc)
                created_tasks += 1
            logger.info("Planned %d connect slots for campaign %s", n_connect, campaign_id)

    # ── Plan FOLLOW_UP slots ──
    has_pending_followup = await db.scheduled_linkedin_tasks.find_one({
        "campaign_id": campaign_id,
        "user_id": user_id,
        "task_type": "follow_up",
        "status": "pending"
    })

    if not has_pending_followup and not messages_exhausted:
        n_followup = max(0, followup_limit - sent_messages)
        if n_followup > 0:
            times = [now] + poisson_slot_times(now, n_followup - 1, 24, start_hour, end_hour, tz_name)
            for t in times:
                task_doc = {
                    "id": generate_id(),
                    "campaign_id": campaign_id,
                    "user_id": user_id,
                    "task_type": "follow_up",
                    "scheduled_at": t,
                    "status": "pending",
                    "created_at": now,
                    "updated_at": now
                }
                await db.scheduled_linkedin_tasks.insert_one(task_doc)
                created_tasks += 1
            logger.info("Planned %d follow-up slots for campaign %s", n_followup, campaign_id)

    # ── Plan CHECK_PENDING slots (capped at 5/day) ──
    has_pending_check = await db.scheduled_linkedin_tasks.find_one({
        "campaign_id": campaign_id,
        "user_id": user_id,
        "task_type": "check_pending",
        "status": "pending"
    })

    if not has_pending_check:
        n_check_due = await db.leads.count_documents({
            "campaign_id": campaign_id,
            "user_id": user_id,
            "linkedin_stage": "pending",
            "next_check_pending_at": {"$lte": now}
        })
        n_check = min(n_check_due, 5)
        if n_check > 0:
            times = [now] + poisson_slot_times(now, n_check - 1, 24, start_hour, end_hour, tz_name)
            for t in times:
                task_doc = {
                    "id": generate_id(),
                    "campaign_id": campaign_id,
                    "user_id": user_id,
                    "task_type": "check_pending",
                    "scheduled_at": t,
                    "status": "pending",
                    "created_at": now,
                    "updated_at": now
                }
                await db.scheduled_linkedin_tasks.insert_one(task_doc)
                created_tasks += 1
            logger.info("Planned %d check_pending slots for campaign %s", n_check, campaign_id)

    return created_tasks
