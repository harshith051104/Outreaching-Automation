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
                                draft_info = process_result.get("auto_dm_result", {})
                                logger.info(
                                    "Post-acceptance draft created for %s (action_id=%s)",
                                    contact_name,
                                    draft_info.get("action_id", "unknown"),
                                )
                        except Exception as proc_err:
                            logger.error(
                                "Failed to process accepted connection for %s: %s",
                                contact_name,
                                proc_err,
                            )

                        # Auto-update outreach tracker: connection accepted milestone
                        try:
                            lead_doc = await db.leads.find_one({
                                "user_id": uid,
                                "$or": [
                                    {"linkedin": linkedin_url},
                                    {"linkedin_url": linkedin_url},
                                ]
                            })
                            if lead_doc and lead_doc.get("id"):
                                from app.services.outreach_tracker_service import update_checkboxes
                                await update_checkboxes(
                                    lead_id=lead_doc["id"],
                                    user_id=uid,
                                    updates={
                                        "linkedin_connection_accepted": True,
                                        "linkedin_first_message_sent": True,
                                    },
                                    trigger_sync=True,
                                )
                        except Exception as tracker_err:
                            logger.debug("Tracker auto-update skipped for %s: %s", contact_name, tracker_err)


            # Trigger auto-reply generation and stage update if there are new unread messages
            if new_msgs and isinstance(new_msgs, list):
                try:
                    from app.services.linkedin_notification_service import create_linkedin_notification
                    from app.services.state_machine_hooks import on_lead_stage_entered

                    for msg_item in new_msgs:
                        if not msg_item.get("linkedin_url"):
                            continue
                        from_name = msg_item.get("from_name", "Unknown")
                        preview = msg_item.get("preview", "")
                        
                        # Find matching lead
                        lead_doc = await db.leads.find_one({
                            "user_id": uid,
                            "$or": [
                                {"linkedin": msg_item["linkedin_url"]},
                                {"linkedin_url": msg_item["linkedin_url"]},
                            ]
                        })
                        if lead_doc:
                            # 1. Update status to linkedin_replied
                            await db.leads.update_one(
                                {"id": lead_doc["id"]},
                                {"$set": {"status": "linkedin_replied", "updated_at": datetime.now(timezone.utc)}}
                            )
                            # 2. Transition decoupled stage to completed (updates checkboxes and sheets)
                            await on_lead_stage_entered(lead_doc["id"], uid, "linkedin", "completed")
                            
                            # 3. Create customized notification matching requirements
                            notif_message = f"{from_name} replied: \"{preview}\""
                            await create_linkedin_notification(
                                user_id=uid,
                                title="New LinkedIn Reply",
                                message=notif_message,
                                reference_id=lead_doc["id"],
                                type_name="linkedin_reply"
                            )
                except Exception as notif_exc:
                    logger.error("Failed to process LinkedIn replies for user %s: %s", uid, notif_exc)

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
        # Store acceptance date in Lead
        await db.leads.update_one(
            {"id": lead["id"]},
            {"$set": {
                "linkedin_connected_at": now,
                "updated_at": now
            }}
        )

        # Transition lead decoupled stage to connected (this updates checkboxes & sheets)
        from app.services.state_machine_hooks import on_lead_stage_entered
        await on_lead_stage_entered(lead["id"], user_id, "linkedin", "connected")

        # Generate notification matching user specifications with WebSocket broadcast
        from app.services.linkedin_notification_service import create_linkedin_notification
        await create_linkedin_notification(
            user_id=user_id,
            title="Connection Accepted",
            message=f"{contact_name} accepted your connection request",
            reference_id=lead["id"],
            type_name="linkedin_accept"
        )

    logger.info("Processed accepted connection: %s (%s)", contact_name, linkedin_url)

    # ── Post-acceptance: generate first message draft ──
    auto_dm_sent = False
    auto_dm_result = None
    action_id = None

    try:
        # Check if auto-dm is enabled (default: True)
        auto_dm_setting = await db.system_settings.find_one({"key": f"linkedin_auto_dm_{user_id}"})
        auto_dm_enabled = auto_dm_setting.get("value", True) if auto_dm_setting else True

        if auto_dm_enabled and lead:
            # Deduplicate: skip if a pending draft already exists for this contact
            existing_draft = await db.linkedin_actions.find_one({
                "user_id": user_id,
                "linkedin_url": linkedin_url,
                "status": "pending_approval",
            })
            if existing_draft:
                logger.info("Post-acceptance draft already exists for %s, skipping", contact_name)
            else:
                # Generate a personalized first-message draft via the orchestrator followup agent
                from app.utils.id_generator import generate_id
                action_id = generate_id()
                lead_name = lead.get("name", contact_name)
                lead_company = lead.get("company", "")
                lead_role = lead.get("role", "")

                logger.info("Generating post-acceptance first-message draft for %s", lead_name)

                try:
                    from orchestrator.engine import get_orchestrator
                    orchestrator = await get_orchestrator()
                    followup_result = await orchestrator.execute_workflow(
                        "LinkedIn Followup Workflow",
                        inputs={
                            "linkedin_url": linkedin_url,
                            "user_id": user_id,
                            "lead_id": lead.get("id", ""),
                            "lead_name": lead_name,
                            "lead_company": lead_company,
                            "lead_role": lead_role,
                            "sequence_number": 1,
                            "timestamp": now.isoformat(),
                        },
                        context={"user_id": user_id},
                    )
                    draft_message = followup_result.get("draft_message", "")
                except Exception as wf_err:
                    logger.warning("Followup workflow failed for post-acceptance draft, using fallback: %s", wf_err)
                    draft_message = ""

                # Fallback: generate a simple personalized greeting if workflow failed
                if not draft_message:
                    first = lead_name.split()[0] if lead_name else "there"
                    draft_message = (
                        f"Hi {first}, thanks for connecting! I'd love to learn more about "
                        f"what you're working on at {lead_company or 'your company'}. "
                        f"Would you be open to a quick chat?"
                    )

                # 1. Save to linkedin_actions (shows in pending queue)
                action_doc = {
                    "id": action_id,
                    "user_id": user_id,
                    "lead_id": lead.get("id", ""),
                    "linkedin_url": linkedin_url,
                    "action_type": "first_message",
                    "status": "pending_approval",
                    "message": draft_message,
                    "created_at": now,
                }
                await db.linkedin_actions.insert_one(action_doc)

                # 2. Save to pending_approvals (chatbot queue integration)
                approval_doc = {
                    "action_id": action_id,
                    "user_id": user_id,
                    "action_type": "linkedin_messages",
                    "description": f"First message to {contact_name} after connection accepted",
                    "count": 1,
                    "items": [linkedin_url],
                    "payload": {
                        "action_id": action_id,
                        "lead_ids": [lead.get("id", "")],
                        "message": draft_message,
                        "linkedin_url": linkedin_url,
                    },
                    "status": "pending",
                    "created_at": now,
                    "updated_at": now,
                }
                await db.pending_approvals.insert_one(approval_doc)

                auto_dm_sent = True
                auto_dm_result = {
                    "action_id": action_id,
                    "draft_message": draft_message,
                    "status": "pending_approval",
                }

                # Create notification so user knows a draft is waiting
                from app.services.linkedin_notification_service import create_linkedin_notification
                await create_linkedin_notification(
                    user_id=user_id,
                    title="First Message Draft Ready",
                    message=f"Draft message for {contact_name} is ready for your approval",
                    reference_id=lead.get("id", ""),
                    type_name="linkedin_draft_ready",
                )

                logger.info("Post-acceptance draft created for %s (action_id=%s)", lead_name, action_id)

    except Exception as draft_err:
        logger.error("Failed to generate post-acceptance draft for %s: %s", contact_name, draft_err)

    return {
        "processed": True,
        "contact_name": contact_name,
        "linkedin_url": linkedin_url,
        "new_stage": "connection_accepted",
        "auto_dm_sent": auto_dm_sent,
        "auto_dm_result": auto_dm_result,
        "action_id": action_id,
    }
