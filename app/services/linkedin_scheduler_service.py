"""
LinkedIn Scheduler Service — Manages scheduled LinkedIn outreach actions.

Capabilities:
- Schedule connection requests and follow-ups for future execution
- Process due actions by invoking the workflow executor
- Enforce daily quotas (max 20 connections, 50 messages per day)
- Track and manage delayed actions

Integrates with the WorkflowExecutor for action execution.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from app.config.mongodb_config import get_database
from app.utils.id_generator import generate_id

logger = logging.getLogger(__name__)

# Daily limits
MAX_DAILY_CONNECTIONS = 20
MAX_DAILY_MESSAGES = 50


async def check_daily_limit(user_id: str, action_type: str) -> Dict[str, Any]:
    """
    Check if the user has remaining quota for the given action type today.

    Args:
        user_id: User's ID.
        action_type: Either 'connection' or 'message'.

    Returns:
        Dict with limit info: remaining, used, max, allowed.
    """
    db = await get_database()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    limit_doc = await db.linkedin_daily_limits.find_one(
        {"user_id": user_id, "date": today}
    )

    if not limit_doc:
        limit_doc = {
            "user_id": user_id,
            "date": today,
            "connections_sent": 0,
            "messages_sent": 0,
        }
        await db.linkedin_daily_limits.insert_one({**limit_doc, "id": generate_id()})

    if action_type == "connection":
        used = limit_doc.get("connections_sent", 0)
        max_limit = MAX_DAILY_CONNECTIONS
    else:
        used = limit_doc.get("messages_sent", 0)
        max_limit = MAX_DAILY_MESSAGES

    remaining = max(0, max_limit - used)

    return {
        "action_type": action_type,
        "used": used,
        "max": max_limit,
        "remaining": remaining,
        "allowed": remaining > 0,
        "date": today,
    }


async def increment_daily_count(user_id: str, action_type: str) -> Dict[str, Any]:
    """
    Increment the daily counter after a successful action.

    Args:
        user_id: User's ID.
        action_type: Either 'connection' or 'message'.
    """
    db = await get_database()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    field = "connections_sent" if action_type == "connection" else "messages_sent"

    result = await db.linkedin_daily_limits.update_one(
        {"user_id": user_id, "date": today},
        {"$inc": {field: 1}},
        upsert=True
    )

    return {"incremented": True, "field": field}


async def schedule_action(
    action_id: str,
    execute_at: datetime,
    user_id: str,
) -> Dict[str, Any]:
    """
    Schedule a pending LinkedIn action for future execution.

    Args:
        action_id: The action document ID in linkedin_actions.
        execute_at: When to execute the action.
        user_id: User's ID.
    """
    db = await get_database()

    from bson import ObjectId
    from bson.errors import InvalidId

    action_query = {"user_id": user_id}
    try:
        action_query["$or"] = [{"id": action_id}, {"_id": ObjectId(action_id)}]
    except InvalidId:
        action_query["id"] = action_id

    result = await db.linkedin_actions.update_one(
        action_query,
        {"$set": {
            "status": "scheduled",
            "scheduled_at": execute_at,
            "updated_at": datetime.now(timezone.utc),
        }}
    )


    if result.modified_count > 0:
        logger.info("Scheduled action %s for %s", action_id, execute_at.isoformat())
        return {"scheduled": True, "action_id": action_id, "execute_at": execute_at.isoformat()}

    return {"scheduled": False, "error": "Action not found"}


async def process_due_actions(user_id: str) -> Dict[str, Any]:
    """
    Find and execute all scheduled actions that are due.

    This is called from the campaign processor loop.
    Delegates execution to the workflow executor.
    """
    from orchestrator.engine import get_orchestrator

    db = await get_database()
    now = datetime.now(timezone.utc)

    # Find due actions
    due_actions = await db.linkedin_actions.find({
        "user_id": user_id,
        "status": "scheduled",
        "scheduled_at": {"$lte": now},
    }).to_list(length=10)

    if not due_actions:
        return {"processed": 0, "actions": []}

    orchestrator = await get_orchestrator()
    processed = []

    for action in due_actions:
        action_type = action.get("action_type")
        action_id = action.get("id")

        # Check daily limits before executing
        if action_type == "connection_request":
            limit_check = await check_daily_limit(user_id, "connection")
        elif action_type in ("message", "followup"):
            limit_check = await check_daily_limit(user_id, "message")
        else:
            limit_check = {"allowed": True}

        if not limit_check.get("allowed"):
            logger.info("Daily limit reached, rescheduling action %s", action_id)
            tomorrow = now + timedelta(days=1)
            tomorrow = tomorrow.replace(hour=9, minute=0, second=0)
            await schedule_action(action_id, tomorrow, user_id)
            continue

        try:
            # Execute the approved action
            if action_type == "connection_request":
                from app.services.linkedin_outreach_service import send_connection_request
                result = await send_connection_request(
                    action.get("linkedin_url"),
                    action.get("message", ""),
                    user_id,
                )
            elif action_type in ("message", "followup"):
                from app.services.linkedin_outreach_service import send_message
                result = await send_message(
                    action.get("linkedin_url"),
                    action.get("message", ""),
                    user_id,
                )
            elif action_type in ("follow", "follow_profile"):
                from app.services.linkedin_outreach_service import follow_profile
                result = await follow_profile(
                    action.get("linkedin_url"),
                    user_id,
                )
            else:
                result = {"success": False, "error": f"Unknown action type: {action_type}"}

            new_status = "executed" if result.get("success") else "failed"
            update_fields = {
                "status": new_status,
                "execution_result": result,
                "executed_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }
            if result.get("success") and action_type == "connection_request":
                if result.get("note_sent") is False or not action.get("message"):
                    update_fields["message_skipped"] = True

            await db.linkedin_actions.update_one(
                {"id": action_id},
                {"$set": update_fields}
            )

            if result.get("success"):
                await increment_daily_count(user_id,
                    "connection" if action_type == "connection_request" else "message")

            processed.append({"action_id": action_id, "status": new_status})

        except Exception as exc:
            logger.error("Failed to process action %s: %s", action_id, exc)
            await db.linkedin_actions.update_one(
                {"id": action_id},
                {"$set": {"status": "failed", "error": str(exc), "updated_at": datetime.now(timezone.utc)}}
            )
            processed.append({"action_id": action_id, "status": "failed"})

    return {"processed": len(processed), "actions": processed}


async def get_queue_status(user_id: str) -> Dict[str, Any]:
    """Get the status of the user's LinkedIn action queue."""
    db = await get_database()

    pending = await db.linkedin_actions.count_documents(
        {"user_id": user_id, "status": "pending_approval"}
    )
    scheduled = await db.linkedin_actions.count_documents(
        {"user_id": user_id, "status": "scheduled"}
    )
    executed = await db.linkedin_actions.count_documents(
        {"user_id": user_id, "status": "executed"}
    )
    failed = await db.linkedin_actions.count_documents(
        {"user_id": user_id, "status": "failed"}
    )

    today_limit = await check_daily_limit(user_id, "connection")
    today_msg_limit = await check_daily_limit(user_id, "message")

    return {
        "pending_approval": pending,
        "scheduled": scheduled,
        "executed_total": executed,
        "failed_total": failed,
        "daily_connections": today_limit,
        "daily_messages": today_msg_limit,
    }
