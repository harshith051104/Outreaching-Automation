"""
LinkedIn Connection Monitor — Detects accepted connections, new replies,
and triggers follow-up workflows automatically.

Flow:
    Connection Accepted → Update Lead Status → Trigger Followup Workflow

Integrates with the existing campaign processor loop in main.py.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from app.config.mongodb_config import get_database

logger = logging.getLogger(__name__)


async def check_for_updates(user_id: str | None = None) -> Dict[str, Any]:
    """
    Check for LinkedIn updates for a user (or all users with active sessions).

    Runs the LinkedIn Monitoring workflow which:
    1. Validates session
    2. Checks for accepted connections
    3. Updates relationship stages
    4. Records tracking events
    5. Stores new messages
    6. Notifies user via WebSocket

    Args:
        user_id: Specific user to check. If None, checks all users with active sessions.

    Returns:
        Summary of updates found.
    """
    db = await get_database()

    if user_id:
        users_to_check = [{"user_id": user_id}]
    else:
        # Find all users with active LinkedIn sessions
        sessions = await db.linkedin_sessions.find(
            {"status": "connected"},
            {"user_id": 1, "_id": 0}
        ).to_list(length=50)
        users_to_check = sessions

    if not users_to_check:
        return {"checked": 0, "updates": []}

    results = []

    for session in users_to_check:
        uid = session.get("user_id")
        if not uid:
            continue

        try:
            from orchestrator.engine import get_orchestrator

            orchestrator = await get_orchestrator()
            workflow_result = await orchestrator.execute_workflow(
                "LinkedIn Monitoring Workflow",
                inputs={
                    "user_id": uid,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                context={"user_id": uid},
            )

            accepted = workflow_result.get("accepted_connections", [])
            new_msgs = workflow_result.get("new_messages", [])

            results.append({
                "user_id": uid,
                "accepted_connections": len(accepted) if isinstance(accepted, list) else 0,
                "new_messages": len(new_msgs) if isinstance(new_msgs, list) else 0,
            })

            logger.info(
                "LinkedIn monitor for user %s: %d accepted, %d new messages",
                uid,
                len(accepted) if isinstance(accepted, list) else 0,
                len(new_msgs) if isinstance(new_msgs, list) else 0,
            )

            # Process each accepted connection - this handles auto-DM for connections sent without note
            if accepted and isinstance(accepted, list):
                for conn in accepted:
                    linkedin_url = conn.get("linkedin_url")
                    contact_name = conn.get("name", "Unknown")
                    if linkedin_url:
                        try:
                            process_result = await process_accepted_connection(uid, linkedin_url, contact_name)
                            if process_result.get("auto_dm_sent"):
                                logger.info(
                                    "Auto-DM sent to %s after connection accepted",
                                    contact_name,
                                )
                        except Exception as proc_err:
                            logger.error(
                                "Failed to process accepted connection for %s: %s",
                                contact_name,
                                proc_err,
                            )

            # Trigger auto-reply generation if there are new unread messages
            if new_msgs and isinstance(new_msgs, list):
                try:
                    # 1. Create dashboard notifications
                    from app.models.notification import Notification
                    for msg_item in new_msgs:
                        if not msg_item.get("linkedin_url"):
                            continue
                        from_name = msg_item.get("from_name", "Unknown")
                        preview = msg_item.get("preview", "")
                        notif_message = f"Received a reply from {from_name}: {preview}"
                        
                        existing_notif = await db.notifications.find_one({
                            "user_id": uid,
                            "reference_type": "linkedin_reply",
                            "reference_id": msg_item["linkedin_url"],
                            "message": notif_message
                        })
                        if not existing_notif:
                            notification = Notification(
                                user_id=uid,
                                sender_id=None,
                                type="linkedin_reply",
                                title="New LinkedIn Reply",
                                message=notif_message,
                                reference_id=msg_item["linkedin_url"],
                                reference_type="linkedin_reply",
                            )
                            await db.notifications.insert_one(notification.to_dict())
                            logger.info("Created dashboard notification for LinkedIn reply from %s", from_name)
                except Exception as notif_exc:
                    logger.error("Failed to create dashboard notification for LinkedIn replies for user %s: %s", uid, notif_exc)

                try:
                    # Check if auto-reply is enabled in settings
                    auto_reply_setting = await db.system_settings.find_one({"key": f"linkedin_auto_reply_{uid}"})
                    auto_reply_enabled = auto_reply_setting.get("value", True) if auto_reply_setting else True
                    
                    if auto_reply_enabled:
                        for msg_item in new_msgs:
                            if not msg_item.get("linkedin_url"):
                                continue
                            
                            # Deduplicate: check if we already have a pending/scheduled followup draft for this contact
                            existing_draft = await db.linkedin_actions.find_one({
                                "user_id": uid,
                                "linkedin_url": msg_item["linkedin_url"],
                                "status": "pending_approval"
                            })
                            if existing_draft:
                                logger.info("LinkedIn monitor: Draft already exists for %s, skipping auto-reply draft", msg_item.get("from_name"))
                                continue
                                
                            # Retrieve lead info to enrich template inputs
                            lead = await db.leads.find_one({
                                "user_id": uid,
                                "$or": [
                                    {"linkedin": msg_item["linkedin_url"]},
                                    {"linkedin_url": msg_item["linkedin_url"]},
                                ]
                            })
                            lead_id = lead.get("id") if lead else ""
                            lead_name = lead.get("name", msg_item["from_name"]) if lead else msg_item["from_name"]
                            lead_company = lead.get("company", "") if lead else ""
                            lead_role = lead.get("role", "") if lead else ""
                            
                            logger.info("LinkedIn monitor: Triggering followup workflow to draft auto-reply for %s", lead_name)
                            await orchestrator.execute_workflow(
                                "LinkedIn Followup Workflow",
                                inputs={
                                    "linkedin_url": msg_item["linkedin_url"],
                                    "user_id": uid,
                                    "lead_id": lead_id,
                                    "lead_name": lead_name,
                                    "lead_company": lead_company,
                                    "lead_role": lead_role,
                                    "sequence_number": 1,
                                    "timestamp": datetime.now(timezone.utc).isoformat(),
                                },
                                context={"user_id": uid},
                            )
                except Exception as auto_exc:
                    logger.error("Failed to run LinkedIn auto-reply engine for user %s: %s", uid, auto_exc)

        except Exception as exc:
            logger.error("LinkedIn monitoring failed for user %s: %s", uid, exc)
            results.append({"user_id": uid, "error": str(exc)})

    return {"checked": len(results), "updates": results}


async def process_accepted_connection(user_id: str, linkedin_url: str, contact_name: str) -> Dict[str, Any]:
    """
    Process a single accepted connection.

    1. Update relationship stage to 'connection_accepted'
    2. Record tracking event
    3. If original connection was sent WITHOUT a note (Premium limit), auto-send the intended message as DM
    """
    db = await get_database()
    now = datetime.now(timezone.utc)

    # Update or create relationship
    await db.linkedin_relationships.update_one(
        {"user_id": user_id, "linkedin_url": linkedin_url},
        {"$set": {
            "current_stage": "connection_accepted",
            "contact_name": contact_name,
            "updated_at": now,
        },
        "$push": {
            "stage_history": {
                "stage": "connection_accepted",
                "timestamp": now,
            }
        }},
        upsert=True,
    )

    # Record tracking event in existing tracking_events collection
    from app.utils.id_generator import generate_id
    await db.tracking_events.insert_one({
        "id": generate_id(),
        "user_id": user_id,
        "event_type": "linkedin_connection_accepted",
        "linkedin_url": linkedin_url,
        "contact_name": contact_name,
        "channel": "linkedin",
        "timestamp": now,
    })

    # Update lead status if lead exists with this LinkedIn URL
    lead = await db.leads.find_one({
        "user_id": user_id,
        "$or": [
            {"linkedin": linkedin_url},
            {"linkedin_url": linkedin_url},
        ]
    })
    if lead:
        await db.leads.update_one(
            {"id": lead["id"]},
            {"$set": {"status": "linkedin_connected", "updated_at": now}}
        )

    # Check if this connection was originally sent WITHOUT a note (due to Premium limit)
    # If so, automatically send the intended message as a DM now that they're connected
    auto_dm_sent = False
    auto_dm_result = None

    try:
        original_action = await db.linkedin_actions.find_one({
            "user_id": user_id,
            "linkedin_url": linkedin_url,
            "action_type": "connection_request",
            "message_skipped": True,
            "status": "executed",
        })

        if original_action and original_action.get("message"):
            intended_message = original_action["message"]
            logger.info(
                "Connection to %s was sent without note. Sending intended message as DM now that they're connected.",
                contact_name,
            )

            # Send the message via Playwright using the subprocess runner
            from app.services.linkedin_outreach_service import send_message
            auto_dm_result = await send_message(
                linkedin_url=linkedin_url,
                message=intended_message,
                user_id=user_id,
            )
            auto_dm_sent = auto_dm_result.get("success", False)

            if auto_dm_sent:
                # Record this DM as a followup action
                await db.linkedin_actions.insert_one({
                    "id": generate_id(),
                    "user_id": user_id,
                    "lead_id": original_action.get("lead_id", ""),
                    "linkedin_url": linkedin_url,
                    "action_type": "followup",
                    "status": "executed",
                    "message": intended_message,
                    "execution_result": auto_dm_result,
                    "created_at": now,
                    "executed_at": now,
                    "auto_sent_on_accept": True,
                    "original_connection_action_id": original_action.get("id", ""),
                })

                # Update relationship stage to message_sent
                await db.linkedin_relationships.update_one(
                    {"user_id": user_id, "linkedin_url": linkedin_url},
                    {"$set": {
                        "current_stage": "message_sent",
                        "updated_at": datetime.now(timezone.utc),
                    },
                    "$push": {
                        "stage_history": {
                            "stage": "message_sent",
                            "timestamp": datetime.now(timezone.utc),
                            "note": "Auto-sent after connection accepted (original note skipped due to Premium limit)"
                        }
                    }},
                )

                logger.info("Auto-DM sent successfully to %s: %s", contact_name, auto_dm_result)
            else:
                logger.warning(
                    "Auto-DM failed for %s (connection accepted): %s",
                    contact_name,
                    auto_dm_result.get("error", "Unknown error"),
                )
        else:
            logger.debug(
                "No skipped message found for %s - no auto-DM needed",
                contact_name,
            )
    except Exception as auto_dm_err:
        logger.error(
            "Error sending auto-DM to %s after connection accepted: %s",
            contact_name,
            auto_dm_err,
        )

    logger.info("Processed accepted connection: %s (%s)", contact_name, linkedin_url)

    return {
        "processed": True,
        "contact_name": contact_name,
        "linkedin_url": linkedin_url,
        "new_stage": "connection_accepted",
        "auto_dm_sent": auto_dm_sent,
        "auto_dm_result": auto_dm_result,
    }
