"""
Multi-Channel Campaign Task Scheduler Service.

Manages the scheduling, database writing, and execution of delay-based sequence steps
(Email, LinkedIn messages, Call reminders, Custom Tasks) using the local asyncio background loop.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from uuid import uuid4

from app.config.mongodb_config import get_database
from app.services.gmail_service import send_email
from app.services.memory_service import AgentMemoryService
from app.models.lead import Lead

logger = logging.getLogger(__name__)


def convert_text_to_html(text: str) -> str:
    """Convert plain text newlines and markdown formatting to HTML."""
    if not text:
        return ""

    import re
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    has_html = "<p>" in text.lower() or "<br" in text.lower() or "<div>" in text.lower()

    if not has_html:
        paragraphs = text.split("\n\n")
        formatted_paragraphs = []
        for p in paragraphs:
            if p.strip():
                formatted_p = p.replace("\n", "<br />")
                formatted_paragraphs.append(f"<p>{formatted_p}</p>")
        text = "\n".join(formatted_paragraphs)

    text = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*(.*?)\*", r"<em>\1</em>", text)

    return text


class TaskSchedulerService:
    """Handles creating, scheduling, and executing sequence steps in an asyncio loop."""

    @staticmethod
    async def schedule_lead_sequence(
        user_id: str,
        campaign_id: str,
        lead_id: str,
        sequence_steps: List[Dict[str, Any]]
    ) -> None:
        """
        Creates and writes pending scheduled tasks in MongoDB for a lead based on sequence offsets.
        Example sequence step: {"channel": "email", "delay_days": 1, "subject_template": "...", "body_template": "..."}
        """
        db = await get_database()
        now = datetime.now(timezone.utc)

        await db.scheduled_tasks.update_many(
            {"lead_id": lead_id, "status": "pending"},
            {"$set": {"status": "cancelled", "updated_at": now}}
        )

        for step in sequence_steps:
            step_num = step.get("step_number") or 1
            delay_days = step.get("delay_days") or 0
            channel = step.get("channel", "email").lower()

            scheduled_time = now + timedelta(days=delay_days)

            task_doc = {
                "id": str(uuid4()),
                "lead_id": lead_id,
                "campaign_id": campaign_id,
                "user_id": user_id,
                "step_number": step_num,
                "channel": channel,
                "status": "pending",
                "scheduled_at": scheduled_time,
                "executed_at": None,
                "data": {
                    "subject_template": step.get("subject_template", ""),
                    "body_template": step.get("body_template", ""),
                    "notes": step.get("notes", "")
                },
                "created_at": now,
                "updated_at": now
            }

            await db.scheduled_tasks.insert_one(task_doc)
            logger.info(
                "Scheduled task for lead %s, step %d (%s) at %s",
                lead_id, step_num, channel, scheduled_time
            )

    @staticmethod
    async def process_pending_tasks() -> None:
        """
        Queries and executes scheduled tasks that are past their execution date.
        This is called periodically inside the asyncio background loop in main.py.
        """
        db = await get_database()
        now = datetime.now(timezone.utc)

        stale_time = now - timedelta(minutes=15)
        recovery_result = await db.scheduled_tasks.update_many(
            {"status": "processing", "updated_at": {"$lte": stale_time}},
            {"$set": {
                "status": "pending",
                "updated_at": now
            }}
        )
        if recovery_result.modified_count > 0:
            logger.info("Scheduler: Recovered %d stuck tasks back to 'pending'", recovery_result.modified_count)

        pending_tasks = await db.scheduled_tasks.find({
            "status": "pending",
            "scheduled_at": {"$lte": now}
        }).to_list(length=100)

        if not pending_tasks:
            return

        logger.info("Scheduler: processing %d pending sequence tasks...", len(pending_tasks))

        for task in pending_tasks:
            task_id = task["id"]
            lead_id = task["lead_id"]
            campaign_id = task["campaign_id"]
            user_id = task["user_id"]
            channel = task["channel"]

            lock_time = datetime.now(timezone.utc)
            lock_res = await db.scheduled_tasks.update_one(
                {"id": task_id, "status": "pending"},
                {"$set": {
                    "status": "processing",
                    "updated_at": lock_time
                }}
            )
            if lock_res.modified_count == 0:
                logger.info("Scheduler: Task %s is already locked/processing. Skipping.", task_id)
                continue

            lead = await db.leads.find_one({"id": lead_id})
            if not lead or lead.get("status") in ("replied", "opted_out", "converted"):
                logger.info("Lead %s responded or has opt-out status. Cancelling task %s.", lead_id, task_id)
                await db.scheduled_tasks.update_one(
                    {"id": task_id},
                    {"$set": {"status": "cancelled", "updated_at": datetime.now(timezone.utc)}}
                )
                continue

            try:
                if channel == "email":
                    await TaskSchedulerService._execute_email_task(task, lead)
                elif channel == "linkedin":
                    await TaskSchedulerService._execute_linkedin_task(task, lead)
                elif channel == "call":
                    await TaskSchedulerService._execute_call_reminder(task, lead)
                elif channel == "task":
                    await TaskSchedulerService._execute_custom_task(task, lead)

                await db.scheduled_tasks.update_one(
                    {"id": task_id},
                    {
                        "$set": {
                            "status": "executed",
                            "executed_at": datetime.now(timezone.utc),
                            "updated_at": datetime.now(timezone.utc)
                        }
                    }
                )
                try:
                    await TaskSchedulerService._reschedule_next_sequence_step(
                        db, campaign_id, lead_id, task.get("step_number") or 1
                    )
                except Exception as reschedule_exc:
                    logger.error("Failed to reschedule next step for lead %s: %s", lead_id, reschedule_exc)
            except Exception as e:
                logger.exception("Failed to execute scheduled task %s: %s", task_id, e)
                await db.scheduled_tasks.update_one(
                    {"id": task_id},
                    {
                        "$set": {
                            "status": "failed",
                            "error": str(e),
                            "updated_at": datetime.now(timezone.utc)
                        }
                    }
                )

    @staticmethod
    async def _reschedule_next_sequence_step(db, campaign_id: str, lead_id: str, current_step_num: int) -> None:
        """
        Adjusts the scheduled_at time of the next sequence step (current_step_num + 1)
        based on the actual execution time of the current step, maintaining the relative delay.
        """
        next_task = await db.scheduled_tasks.find_one({
            "campaign_id": campaign_id,
            "lead_id": lead_id,
            "step_number": current_step_num + 1,
            "status": "pending"
        })
        if not next_task:
            return

        campaign = await db.campaigns.find_one({"id": campaign_id})
        if not campaign or not campaign.get("sequence_steps"):
            return

        steps = campaign["sequence_steps"]
        current_delay = 0
        next_delay = 0
        current_found = False
        next_found = False

        for step in steps:
            step_num = step.get("step_number") or 1
            if step_num == current_step_num:
                current_delay = step.get("delay_days") or 0
                current_found = True
            elif step_num == current_step_num + 1:
                next_delay = step.get("delay_days") or 0
                next_found = True

        if current_found and next_found:
            delta_days = next_delay - current_delay
            if delta_days < 0:
                delta_days = 0
            
            new_scheduled_at = datetime.now(timezone.utc) + timedelta(days=delta_days)
            await db.scheduled_tasks.update_one(
                {"id": next_task["id"]},
                {"$set": {
                    "scheduled_at": new_scheduled_at,
                    "updated_at": datetime.now(timezone.utc)
                }}
            )
            logger.info(
                "Rescheduled next task %s (step %d) for lead %s to %s (delta: %d days)",
                next_task["id"], current_step_num + 1, lead_id, new_scheduled_at, delta_days
            )

    @staticmethod
    async def _execute_email_task(task: Dict[str, Any], lead: Dict[str, Any]) -> None:
        """Personalises and sends an email via Gmail API."""
        from app.services.email_service import create_email, send_campaign_email
        from app.schemas.email import EmailCreate
        from app.utils.id_generator import generate_tracking_id
        from app.tasks.campaign_tasks import _format_template

        logger.info("Executing scheduled Email task for lead: %s", lead["email"])

        db = await get_database()
        campaign = await db.campaigns.find_one({"id": task["campaign_id"]})
        gmail_id = campaign.get("gmail_account_id") if campaign else ""

        if gmail_id:
            gmail_acct = await db.gmail_accounts.find_one({"id": gmail_id, "is_active": True})
            if not gmail_acct:
                gmail_id = ""

        if not gmail_id:
            active_acct = await db.gmail_accounts.find_one({"user_id": task["user_id"], "is_active": True})
            gmail_id = active_acct["id"] if active_acct else ""

        sender_name = ""
        sender_email = ""
        if gmail_id:
            gmail_acct = await db.gmail_accounts.find_one({"id": gmail_id})
            if gmail_acct:
                sender_name = gmail_acct.get("name", "")
                sender_email = gmail_acct.get("email", "")

        lead_email = lead.get("email", "").strip()
        if not lead_email:
            logger.warning("Scheduled email task skipped for lead %s — no email address found.", lead.get("id"))
            return

        subject_template = task["data"].get("subject_template", "Outreach")
        body_template = task["data"].get("body_template", "Hi {{first_name}}")

        lead_name = lead.get("name", "") or lead.get("first_name", "") or ""
        subject = _format_template(subject_template, lead, lead_name, sender_name, sender_email)
        body = _format_template(body_template, lead, lead_name, sender_name, sender_email)
        
        # Convert plain text newlines and markdown formatting to HTML
        body_html = convert_text_to_html(body)

        if gmail_id:
            tracking_id = generate_tracking_id()
            email_data = EmailCreate(
                campaign_id=task["campaign_id"],
                lead_id=lead["id"],
                gmail_account_id=gmail_id,
                to=lead_email,
                subject=subject,
                body_html=body_html,
                sequence_number=task.get("step_number") or 1
            )
            
            email_doc = await create_email(
                user_id=task["user_id"],
                data=email_data,
                tracking_id=tracking_id
            )
            
            await send_campaign_email(email_doc["id"])

            # Auto-update tracker: email_sent milestone
            try:
                from app.services.outreach_tracker_service import update_checkboxes
                await update_checkboxes(
                    lead_id=lead["id"],
                    user_id=task["user_id"],
                    updates={"email_sent": True},
                    trigger_sync=False,
                )
            except Exception:
                pass

            await AgentMemoryService.add_email_to_memory(
                lead_id=lead["id"],
                user_id=task["user_id"],
                email_subject=subject,
                email_body=body
            )
            await db.campaigns.update_one(
                {"id": task["campaign_id"]},
                {"$inc": {"sent_count": 1}}
            )

            # Notify campaign owner
            try:
                from app.services.notification_service import notify
                await notify(
                    user_id=task["user_id"],
                    type="email_sent",
                    title="Sequence Email Sent",
                    message=f"Step {task.get('step_number', 1)} email sent to {lead_email}.",
                    reference_id=task["campaign_id"],
                    reference_type="campaign",
                )
            except Exception:
                pass

            logger.info("Scheduled email sent to %s successfully.", lead_email)
        else:
            raise Exception("No active Gmail account found connected for user to send sequence email")

    @staticmethod
    async def _execute_linkedin_task(task: Dict[str, Any], lead: Dict[str, Any]) -> None:
        """Generates copy for LinkedIn connection requests/messages and saves it for manual export."""
        logger.info("Executing scheduled LinkedIn task copy generation for %s", lead["name"])
        db = await get_database()
        from app.tasks.campaign_tasks import _format_template

        campaign = await db.campaigns.find_one({"id": task["campaign_id"]})
        gmail_id = campaign.get("gmail_account_id") if campaign else ""

        if not gmail_id:
            active_acct = await db.gmail_accounts.find_one({"user_id": task["user_id"], "is_active": True})
            gmail_id = active_acct["id"] if active_acct else ""

        sender_name = ""
        sender_email = ""
        if gmail_id:
            gmail_acct = await db.gmail_accounts.find_one({"id": gmail_id})
            if gmail_acct:
                sender_name = gmail_acct.get("name", "")
                sender_email = gmail_acct.get("email", "")

        body_template = task["data"].get("body_template", "Hi {{first_name}}, let's connect!")
        lead_name = lead.get("name", "") or lead.get("first_name", "") or ""
        message_body = _format_template(body_template, lead, lead_name, sender_name, sender_email)

        outreach_record = {
            "id": str(uuid4()),
            "lead_id": lead["id"],
            "campaign_id": task["campaign_id"],
            "user_id": task["user_id"],
            "channel": "linkedin",
            "status": "pending_manual_export",
            "message_body": message_body,
            "created_at": datetime.now(timezone.utc)
        }
        await db.outreach.insert_one(outreach_record)

        # Auto-update tracker: linkedin_connection_sent milestone
        try:
            from app.services.outreach_tracker_service import update_checkboxes
            await update_checkboxes(
                lead_id=lead["id"],
                user_id=task["user_id"],
                updates={"linkedin_connection_sent": True},
                trigger_sync=False,
            )
        except Exception:
            pass

        await AgentMemoryService.add_note_to_memory(
            lead_id=lead["id"],
            user_id=task["user_id"],
            note_text=f"Generated LinkedIn Message: '{message_body}' (Saved for manual export)"
        )

    @staticmethod
    async def _execute_call_reminder(task: Dict[str, Any], lead: Dict[str, Any]) -> None:
        """Writes call reminder entry to manual action checklist."""
        logger.info("Creating Call action reminder for lead %s", lead["name"])
        db = await get_database()

        reminder = {
            "id": str(uuid4()),
            "lead_id": lead["id"],
            "campaign_id": task["campaign_id"],
            "user_id": task["user_id"],
            "channel": "call",
            "status": "action_required",
            "notes": task["data"].get("notes", f"Call lead {lead['name']} at {lead.get('company') or 'company'}"),
            "created_at": datetime.now(timezone.utc)
        }
        await db.outreach.insert_one(reminder)

        await AgentMemoryService.add_note_to_memory(
            lead_id=lead["id"],
            user_id=task["user_id"],
            note_text="Created scheduled manual call reminder task."
        )

    @staticmethod
    async def _execute_custom_task(task: Dict[str, Any], lead: Dict[str, Any]) -> None:
        """Writes custom action reminder to manual checklists."""
        logger.info("Creating custom task action reminder for %s", lead["name"])
        db = await get_database()

        custom_task = {
            "id": str(uuid4()),
            "lead_id": lead["id"],
            "campaign_id": task["campaign_id"],
            "user_id": task["user_id"],
            "channel": "task",
            "status": "action_required",
            "notes": task["data"].get("notes", "Check lead social posts or review enrichment state"),
            "created_at": datetime.now(timezone.utc)
        }
        await db.outreach.insert_one(custom_task)

        await AgentMemoryService.add_note_to_memory(
            lead_id=lead["id"],
            user_id=task["user_id"],
            note_text="Created scheduled custom action item."
        )