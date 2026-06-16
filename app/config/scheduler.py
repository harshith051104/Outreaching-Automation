"""
APScheduler configuration for running periodic background tasks within FastAPI.
Replaces the monolithic while-True loop and provides an in-app alternative to Celery/Redis.
"""

import logging
from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

# Initialize the scheduler
scheduler = AsyncIOScheduler()

async def campaign_and_sequence_job():
    """Processes active campaigns: schedules sequence steps for new leads,
    runs TaskSchedulerService, and resumes visual flow runs."""
    try:
        from app.config.mongodb_config import get_database
        from app.services.task_scheduler_service import TaskSchedulerService
        from app.services.flow_execution_service import FlowExecutionService

        db = await get_database()
        now = datetime.now(timezone.utc)

        # 1. Process active campaigns and schedule lead sequences
        active_campaigns = await db.campaigns.find({"status": "active"}).to_list(length=100)

        for campaign in active_campaigns:
            pending_leads = await db.leads.find({
                "campaign_id": campaign["id"],
                "status": "new"
            }).to_list(length=50)

            if pending_leads:
                logger.info("Scheduler Job: Scheduling sequences for %d new leads in campaign '%s'",
                            len(pending_leads), campaign.get("name"))

                steps = campaign.get("sequence_steps") or [
                    {"step_number": 1, "channel": "linkedin", "delay_days": 0,
                     "body_template": "Hi {{first_name}}, I'd like to connect."},
                    {"step_number": 2, "channel": "email", "delay_days": 3,
                     "subject_template": campaign.get("subject_template") or "Quick question",
                     "body_template": campaign.get("body_template") or "Hi {{first_name}},"},
                    {"step_number": 3, "channel": "linkedin", "delay_days": 6,
                     "body_template": "Hi {{first_name}}, I sent you a message earlier. Would love to connect."},
                    {"step_number": 4, "channel": "email", "delay_days": 10,
                     "subject_template": "Re: " + (campaign.get("subject_template") or "Quick question"),
                     "body_template": "Hi {{first_name}},\n\nJust following up on my previous message. Any thoughts?"},
                    {"step_number": 5, "channel": "linkedin", "delay_days": 15,
                     "body_template": "Hi {{first_name}}, great post! Just engaged with it."},
                    {"step_number": 6, "channel": "email", "delay_days": 20,
                     "subject_template": "{{company}} + {{sender_name}}",
                     "body_template": "Hi {{first_name}},\n\nI noticed {{company}} has been growing rapidly. We've helped similar companies achieve great results.\n\nWould love to share how we could help.\n\nBest"},
                    {"step_number": 7, "channel": "email", "delay_days": 28,
                     "subject_template": "One last try",
                     "body_template": "Hi {{first_name}},\n\nI hope this finds you well. I'll respect your time and won't reach out again after this.\n\nBest"}
                ]

                for lead in pending_leads:
                    lead_id = lead.get("id") or str(lead["_id"])
                    await TaskSchedulerService.schedule_lead_sequence(
                        user_id=campaign["user_id"],
                        campaign_id=campaign["id"],
                        lead_id=lead_id,
                        sequence_steps=steps
                    )
                    await db.leads.update_one(
                        {"_id": lead["_id"]},
                        {"$set": {"status": "contacted", "updated_at": now}}
                    )

        # 2. Process scheduled tasks
        await TaskSchedulerService.process_pending_tasks()

        # 3. Process visual flow delay triggers
        try:
            await FlowExecutionService.resume_delay_runs()
        except Exception as fe_exc:
            logger.error("Flow execution delay runner failed: %s", fe_exc)

        # 4. Trigger active flows automatically in background
        try:
            active_flows = await db.campaign_flows.find({"status": "active"}).to_list(length=50)
            for flow in active_flows:
                await FlowExecutionService.start_flow(flow["id"], flow["user_id"], is_manual=False)
        except Exception as flow_sched_exc:
            logger.error("Background flow execution trigger runner failed: %s", flow_sched_exc)

    except Exception as exc:
        logger.error("Scheduler Job Error (campaign_and_sequence_job): %s", exc)

async def followup_job():
    """Processes pending email followups."""
    try:
        from app.tasks.followup_tasks import process_pending_followups
        await process_pending_followups()
    except Exception as exc:
        logger.error("Scheduler Job Error (followup_job): %s", exc)

async def poll_gmail_replies_job():
    """Polls Gmail inbox for replies and runs classification."""
    try:
        logger.info("Scheduler Job: Polling Gmail for replies...")
        from app.tasks.tracking_tasks import poll_gmail_replies
        await poll_gmail_replies()
    except Exception as exc:
        logger.error("Scheduler Job Error (poll_gmail_replies_job): %s", exc)

async def refresh_analytics_job():
    """Refreshes analytics across all campaigns."""
    try:
        from app.tasks.analytics_tasks import refresh_all_campaign_analytics
        await refresh_all_campaign_analytics()
    except Exception as exc:
        logger.error("Scheduler Job Error (refresh_analytics_job): %s", exc)

async def poll_linkedin_job():
    """Runs LinkedIn Connection Monitor checking for connection accepts, unread messages,
    and updates relationship stages."""
    try:
        logger.info("Scheduler Job: Running LinkedIn Connection Monitor...")
        from app.services.linkedin_connection_monitor import check_for_updates
        await check_for_updates()
    except Exception as exc:
        logger.error("Scheduler Job Error (poll_linkedin_job): %s", exc)

async def process_linkedin_actions_job():
    """Processes pending LinkedIn actions (connection requests, DMs) due for execution."""
    try:
        from app.services.linkedin_scheduler_service import process_due_actions
        from app.config.mongodb_config import get_database

        db = await get_database()
        active_sessions = await db.linkedin_sessions.find(
            {"status": "connected"}, {"user_id": 1, "_id": 0}
        ).to_list(length=50)

        for sess in active_sessions:
            uid = sess.get("user_id")
            if uid:
                await process_due_actions(uid)
    except Exception as exc:
        logger.error("Scheduler Job Error (process_linkedin_actions_job): %s", exc)


def start_scheduler():
    """Start APScheduler and register interval-based background jobs."""
    if scheduler.running:
        logger.warning("APScheduler is already running.")
        return

    # Campaign & sequences processor: run every 30 seconds
    scheduler.add_job(
        campaign_and_sequence_job,
        trigger=IntervalTrigger(seconds=30),
        id="campaign_processor",
        replace_existing=True
    )

    # Process email followups: run every 1 minute
    scheduler.add_job(
        followup_job,
        trigger=IntervalTrigger(minutes=1),
        id="followup_processor",
        replace_existing=True
    )

    # Process scheduled LinkedIn actions (connection requests/DMs queue): run every 1 minute
    scheduler.add_job(
        process_linkedin_actions_job,
        trigger=IntervalTrigger(minutes=1),
        id="linkedin_actions_processor",
        replace_existing=True
    )

    # Poll Gmail replies: run every 5 minutes
    scheduler.add_job(
        poll_gmail_replies_job,
        trigger=IntervalTrigger(minutes=5),
        id="gmail_reply_poller",
        replace_existing=True
    )

    # Poll LinkedIn inbox and connection updates: run every 15 minutes (to prevent rate limits)
    scheduler.add_job(
        poll_linkedin_job,
        trigger=IntervalTrigger(minutes=15),
        id="linkedin_inbox_poller",
        replace_existing=True
    )

    # Refresh campaign analytics: run every 15 minutes
    scheduler.add_job(
        refresh_analytics_job,
        trigger=IntervalTrigger(minutes=15),
        id="analytics_refresher",
        replace_existing=True
    )

    scheduler.start()
    logger.info("APScheduler started successfully and periodic jobs registered.")


def shutdown_scheduler():
    """Stop APScheduler background tasks."""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("APScheduler shut down successfully.")
