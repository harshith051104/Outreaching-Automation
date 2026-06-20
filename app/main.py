"""
AI Outreach Platform v2 - FastAPI Application Entry Point.

Initialises the async MongoDB connection, registers all API routers,
configures CORS, starts the metadata-driven orchestrator, and runs
the campaign processor background loop.
"""

import sys
import signal

if sys.platform == "win32":
    for sig in ["SIGHUP", "SIGQUIT", "SIGTSTP", "SIGCONT", "SIGUSR1", "SIGUSR2"]:
        if not hasattr(signal, sig):
            setattr(signal, sig, 1)

    import platform
    from collections import namedtuple
    UnameResult = namedtuple('uname_result', ['system', 'node', 'release', 'version', 'machine'])
    platform.uname = lambda: UnameResult('Windows', 'localhost', '10', '10.0.0', 'AMD64')

    import asyncio
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except AttributeError:
        pass

import logging
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from app.config.mongodb_config import mongodb_client

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle: connect on startup, disconnect on shutdown."""
    await mongodb_client.connect()
    await mongodb_client.create_indexes()

    # Run database migration for existing leads missing the 'id' field
    try:
        from app.config.mongodb_config import get_database
        db = await get_database()
        leads_cursor = db.leads.find({"id": {"$exists": False}})
        migrated_count = 0
        async for lead_doc in leads_cursor:
            _id = lead_doc.get("_id")
            if _id:
                await db.leads.update_one(
                    {"_id": _id},
                    {"$set": {"id": str(_id)}}
                )
                migrated_count += 1
        if migrated_count > 0:
            logger.info("Database Migration: Backfilled 'id' field for %d existing leads.", migrated_count)
    except Exception as exc:
        logger.error(f"Failed to run lead ID migration: {exc}")

    # Run database migration: fix campaign_ids that were saved as names instead of UUIDs
    try:
        import re
        from app.config.mongodb_config import get_database
        db = await get_database()
        campaigns = await db.campaigns.find({"status": {"$ne": "deleted"}}).to_list(length=1000)
        migrated_leads_count = 0
        for campaign in campaigns:
            camp_name = campaign.get("name")
            camp_id = campaign.get("id")
            if camp_name and camp_id:
                leads_to_fix = db.leads.find({
                    "campaign_id": {"$regex": f"^{re.escape(camp_name)}$", "$options": "i"}
                })
                async for lead_doc in leads_to_fix:
                    await db.leads.update_one(
                        {"_id": lead_doc["_id"]},
                        {"$set": {"campaign_id": camp_id, "updated_at": datetime.now(timezone.utc)}}
                    )
                    migrated_leads_count += 1
                
                # Update total_leads count for the campaign
                total_leads = await db.leads.count_documents({"campaign_id": camp_id})
                await db.campaigns.update_one(
                    {"id": camp_id},
                    {"$set": {"total_leads": total_leads}}
                )
        if migrated_leads_count > 0:
            logger.info("Database Migration: Fixed campaign_id for %d leads.", migrated_leads_count)
    except Exception as exc:
        logger.error(f"Failed to run campaign ID lead migration: {exc}")

    # Run database migration: expedite pending email tasks for active/draft Market Stakeholder campaigns
    try:
        from app.config.mongodb_config import get_database
        from datetime import datetime, timedelta, timezone
        db = await get_database()
        campaigns_to_fix = await db.campaigns.find({
            "name": {"$in": ["Market Stakeholder", "Business Stakeholder"]},
            "status": {"$ne": "deleted"}
        }).to_list(length=100)
        camp_ids = [c["id"] for c in campaigns_to_fix if c.get("id")]
        if camp_ids:
            result = await db.scheduled_tasks.update_many(
                {
                    "campaign_id": {"$in": camp_ids},
                    "status": "pending",
                    "channel": "email"
                },
                {
                    "$set": {
                        "scheduled_at": datetime.now(timezone.utc) - timedelta(hours=1),
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )
            if result.modified_count > 0:
                logger.info("Database Migration: Expedited %d pending email tasks to run immediately.", result.modified_count)
    except Exception as exc:
        logger.error(f"Failed to run scheduled tasks expedition migration: {exc}")

    try:
        from app.services.qdrant_service import ensure_all_collections
        ensure_all_collections()
    except Exception as exc:
        logger.warning(f"Could not bootstrap Qdrant collections: {exc}")

    try:
        from orchestrator.engine import get_orchestrator
        orchestrator = await get_orchestrator()
        logger.info("Metadata-driven orchestrator initialized")
    except Exception as exc:
        logger.warning(f"Could not initialize orchestrator: {exc}")

    # Initialize LLM toggle state from database
    try:
        from app.config.mongodb_config import get_database
        from app.config.groq_config import set_llm_section_disabled
        db = await get_database()
        
        # Initialize each section
        sections = ["linkedin", "reply_monitor", "campaigns", "chatbot"]
        for section in sections:
            settings_doc = await db.system_settings.find_one({"key": f"disable_llm_{section}"})
            if settings_doc:
                set_llm_section_disabled(section, settings_doc.get("value", False))
                logger.info("LLM disabled state for '%s' initialized from DB to: %s", section, settings_doc.get("value", False))
            else:
                # Check for legacy global toggle as fallback
                global_doc = await db.system_settings.find_one({"key": "disable_llm"})
                if global_doc:
                    set_llm_section_disabled(section, global_doc.get("value", False))
                    logger.info("LLM disabled state for '%s' initialized from fallback DB to: %s", section, global_doc.get("value", False))
    except Exception as exc:
        logger.warning("Failed to initialize LLM toggle state from database: %s", exc)

    # Pre-warm active LinkedIn sessions in background
    try:
        from app.services.linkedin_session_manager import restore_sessions_on_startup
        asyncio.create_task(restore_sessions_on_startup())
    except Exception as exc:
        logger.error(f"Failed to start pre-warming LinkedIn sessions: {exc}")

    logger.info("Application started at %s", datetime.now(timezone.utc).isoformat())

    campaign_processor_task = asyncio.create_task(_campaign_processor_loop())
    sheets_sync_task = asyncio.create_task(_sheets_sync_loop())

    yield

    campaign_processor_task.cancel()
    sheets_sync_task.cancel()
    try:
        await campaign_processor_task
    except asyncio.CancelledError:
        pass
    try:
        await sheets_sync_task
    except asyncio.CancelledError:
        pass

    # Clean up warm sessions on shutdown
    try:
        from app.services.linkedin_session_manager import close_all_active_sessions
        await close_all_active_sessions()
    except Exception as exc:
        logger.error(f"Error during shutdown of LinkedIn sessions: {exc}")

    await mongodb_client.disconnect()
    logger.info("Application shutdown complete.")


async def _campaign_processor_loop():
    """
    Background loop that periodically processes active campaigns, checks replies,
    handles followups, and refreshes analytics.

    Runs every 30 seconds, finds active campaigns with pending leads,
    triggers email sending, processes followups, polls Gmail replies, and refreshes analytics.
    """
    import asyncio

    await asyncio.sleep(10)

    while True:
        try:
            from app.config.mongodb_config import get_database
            from app.services.task_scheduler_service import TaskSchedulerService
            from app.tasks.tracking_tasks import poll_gmail_replies
            from app.tasks.followup_tasks import process_pending_followups
            from app.tasks.analytics_tasks import refresh_all_campaign_analytics

            db = await get_database()
            now = datetime.now(timezone.utc)

            active_campaigns = await db.campaigns.find({"status": "active"}).to_list(length=100)

            for campaign in active_campaigns:
                pending_leads = await db.leads.find({
                    "campaign_id": campaign["id"],
                    "status": "new"
                }).to_list(length=50)

                if pending_leads:
                    logger.info("Scheduler: Scheduling sequences for %d new leads in campaign '%s'",
                               len(pending_leads), campaign.get("name"))

                    if campaign.get("subject_template") or campaign.get("body_template"):
                        steps = campaign.get("sequence_steps") or [
                            {"step_number": 1, "channel": "email", "delay_days": 0,
                             "subject_template": campaign.get("subject_template") or "Quick question",
                             "body_template": campaign.get("body_template") or "Hi {{first_name}},"}
                        ]
                    else:
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

            # Process scheduled campaign tasks
            await TaskSchedulerService.process_pending_tasks()

            # Process scheduled followup tasks
            await process_pending_followups()



            # Poll Gmail for replies
            logger.info("Scheduler: Polling Gmail for campaign replies...")
            await poll_gmail_replies()

            # Refresh analytics
            await refresh_all_campaign_analytics()

            # ── LinkedIn Monitoring ────────────────────────────────────
            try:
                from app.services.linkedin_connection_monitor import check_for_updates
                await check_for_updates()
            except Exception as li_exc:
                logger.debug("LinkedIn monitoring skipped: %s", li_exc)

            try:
                from app.services.linkedin_scheduler_service import process_due_actions
                # Process scheduled LinkedIn actions for users with active sessions
                from app.config.mongodb_config import get_database as _get_db
                _db = await _get_db()
                active_sessions = await _db.linkedin_sessions.find(
                    {"status": "connected"}, {"user_id": 1, "_id": 0}
                ).to_list(length=50)
                for sess in active_sessions:
                    if sess.get("user_id"):
                        await process_due_actions(sess["user_id"])
            except Exception as sched_exc:
                logger.debug("LinkedIn scheduler skipped: %s", sched_exc)

        except Exception as exc:
            logger.exception("Campaign processor loop error: %s", exc)

        await asyncio.sleep(30)


async def _sheets_sync_loop():
    """
    Background loop that pulls Google Sheet updates into MongoDB every 15 minutes.
    Skipped silently if no users have configured Google Sheets integration.
    """
    import asyncio
    await asyncio.sleep(60)  # Initial delay to let the app stabilize

    while True:
        try:
            from app.services.sheets_sync_service import sync_all_users
            await sync_all_users()
        except Exception as exc:
            logger.error("Sheets sync loop error: %s", exc)
        await asyncio.sleep(900)  # 15 minutes


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    from app.config.settings import settings

    app = FastAPI(
        title=settings.APP_NAME,
        description="AI-powered outreach automation platform with metadata-driven agents, Gmail integration, campaign management, and analytics.",
        version="2.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    try:
        from app.middleware.rate_limiter import RateLimitMiddleware
        app.add_middleware(RateLimitMiddleware)
    except ImportError:
        pass

    @app.middleware("http")
    async def clean_double_slashes(request: Request, call_next):
        path = request.scope.get("path", "")
        if "//" in path:
            cleaned = path
            while "//" in cleaned:
                cleaned = cleaned.replace("//", "/")
            request.scope["path"] = cleaned
            if "raw_path" in request.scope:
                request.scope["raw_path"] = cleaned.encode("utf-8")
        return await call_next(request)

    @app.middleware("http")
    async def add_no_cache_header(request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/api"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled exception: %s", exc)
        try:
            import traceback
            with open("c:/Users/sriha/My work/Outreach/error_traceback.txt", "a", encoding="utf-8") as f:
                f.write(f"\n--- ERROR AT {datetime.now().isoformat()} ---\n")
                f.write(f"URL: {request.url}\n")
                f.write(f"Method: {request.method}\n")
                f.write(traceback.format_exc())
                f.write("-" * 40 + "\n")
        except Exception as e:
            logger.error("Failed to write to error_traceback.txt: %s", e)
        return JSONResponse(
            status_code=500,
            content={"detail": f"Internal server error: {str(exc)}"},
        )


    @app.get("/health")
    async def health_check():
        return {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": "2.0.0",
            "architecture": "metadata-driven",
        }

    @app.get("/health/linkedin_diagnose")
    async def linkedin_diagnose():
        from app.config.mongodb_config import get_database
        db = await get_database()
        sessions = await db.linkedin_sessions.find({}).to_list(length=10)
        return {
            "sessions": [
                {
                    "user_id": s.get("user_id"),
                    "status": s.get("status"),
                    "account_name": s.get("account_name"),
                    "last_validated_at": s.get("last_validated_at"),
                    "updated_at": s.get("updated_at"),
                    "has_cookies": bool(s.get("cookies_encrypted"))
                }
                for s in sessions
            ]
        }

    from app.api.auth_routes import router as auth_router
    from app.api.gmail_routes import router as gmail_router
    from app.api.campaign_routes import router as campaign_router
    from app.api.lead_routes import router as lead_router
    from app.api.tracking_routes import router as tracking_router
    from app.api.analytics_routes import router as analytics_router
    from app.api.ai_routes import router as ai_router
    from app.api.followup_routes import router as followup_router
    from app.api.chatbot_routes import router as chatbot_router
    from app.api.reply_monitor_routes import router as reply_monitor_router
    from app.api.webhook_routes import router as webhook_router
    from app.api.lead_management_routes import router as lead_management_router
    from app.api.chat_session_routes import router as chat_session_router
    from app.api.file_upload_routes import router as file_upload_router
    from app.api.discovery_routes import router as discovery_router
    from app.api.enrichment_routes import router as enrichment_router
    from app.api.signal_routes import router as signal_router
    from app.api.pitch_deck_routes import router as pitch_deck_router
    from app.api.linkedin_routes import router as linkedin_router
    from app.api.inbox_placement_routes import router as inbox_placement_router
    from app.api.task_routes import router as task_router
    from app.api.task_comment_routes import router as task_comment_router
    from app.api.suggestion_routes import router as suggestion_router
    from app.api.notification_routes import router as notification_router
    from app.api.task_tracker_dashboard import router as task_tracker_dashboard_router

    # ── New platform upgrade routers ──────────────────────────────────────
    from app.api.integrations_routes import router as integrations_router
    from app.api.outreach_tracker_routes import router as outreach_tracker_router
    from app.api.chatbot_approval_routes import router as chatbot_approval_router

    api_prefix = settings.API_PREFIX

    app.include_router(auth_router, prefix=api_prefix, tags=["Authentication"])
    app.include_router(gmail_router, prefix=api_prefix, tags=["Gmail"])
    app.include_router(campaign_router, prefix=api_prefix, tags=["Campaigns"])
    app.include_router(lead_router, prefix=api_prefix, tags=["Leads"])
    app.include_router(tracking_router, prefix=api_prefix, tags=["Tracking"])
    app.include_router(analytics_router, prefix=api_prefix, tags=["Analytics"])
    app.include_router(ai_router, prefix=api_prefix, tags=["AI"])
    app.include_router(followup_router, prefix=api_prefix, tags=["Follow-ups"])
    app.include_router(chatbot_router, prefix=api_prefix, tags=["Chatbot"])
    app.include_router(reply_monitor_router, prefix=api_prefix, tags=["Reply Monitor"])
    app.include_router(webhook_router, prefix=api_prefix, tags=["Webhooks"])
    app.include_router(lead_management_router, prefix=api_prefix, tags=["Lead Management"])
    app.include_router(chat_session_router, prefix=api_prefix, tags=["Chat Sessions"])
    app.include_router(file_upload_router, prefix=api_prefix, tags=["File Upload"])
    app.include_router(discovery_router, prefix=api_prefix, tags=["Lead Discovery"])
    app.include_router(enrichment_router, prefix=api_prefix, tags=["Contact Enrichment"])
    app.include_router(signal_router, prefix=api_prefix, tags=["Signal Intelligence"])
    app.include_router(pitch_deck_router, prefix=api_prefix, tags=["Pitch Decks"])
    app.include_router(linkedin_router, prefix=api_prefix, tags=["LinkedIn"])
    app.include_router(inbox_placement_router, prefix=api_prefix, tags=["Inbox Placement"])
    app.include_router(task_router, prefix=api_prefix)
    app.include_router(task_comment_router, prefix=api_prefix)
    app.include_router(suggestion_router, prefix=api_prefix)
    app.include_router(notification_router, prefix=api_prefix)
    app.include_router(task_tracker_dashboard_router, prefix=api_prefix)

    # ── New platform upgrade routers ──────────────────────────────────────
    app.include_router(integrations_router, prefix=api_prefix, tags=["Integrations"])
    app.include_router(outreach_tracker_router, prefix=api_prefix, tags=["Outreach Tracker"])
    app.include_router(chatbot_approval_router, prefix=api_prefix, tags=["Chatbot Approvals"])

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)