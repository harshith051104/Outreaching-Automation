"""
Celery worker entry point for background task processing.

Initialises Celery with Redis as broker/backend and registers
all task modules for campaign execution, follow-ups, reply polling,
and analytics refresh.
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

from app.config.redis_config import celery_app
from app.config.settings import settings

celery_app.conf.update(
    include=[
        "app.tasks.campaign_tasks",
        "app.tasks.followup_tasks",
        "app.tasks.tracking_tasks",
        "app.tasks.analytics_tasks",
        "app.tasks.linkedin_tasks",
    ]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    date_parser="%Y-%m-%d %H:%M:%S",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_time_limit=300,
    task_soft_time_limit=240,
    result_expires=3600,
    result_extended=True,
    beat_schedule={
        "process-active-campaigns-every-30-seconds": {
            "task": "app.tasks.campaign_tasks.process_active_campaigns",
            "schedule": 30.0,
        },
        "process-scheduled-campaign-tasks-every-30-seconds": {
            "task": "app.tasks.campaign_tasks.process_scheduled_campaign_tasks",
            "schedule": 30.0,
        },
        "poll-replies-every-5-minutes": {
            "task": "app.tasks.tracking_tasks.poll_gmail_replies",
            "schedule": 300.0,
        },
        "process-followups-every-minute": {
            "task": "app.tasks.followup_tasks.process_pending_followups",
            "schedule": 60.0,
        },
        "update-analytics-every-15-minutes": {
            "task": "app.tasks.analytics_tasks.refresh_all_campaign_analytics",
            "schedule": 900.0,
        },
        "poll-linkedin-every-15-minutes": {
            "task": "app.tasks.linkedin_tasks.poll_linkedin_inbox",
            "schedule": 900.0,
        },
    },
)


@celery_app.task(bind=True, name="health_check")
def health_check(self):
    """Simple health check task to verify Celery is running."""
    return {"status": "ok", "task_id": self.request.id, "architecture": "metadata-driven"}


if __name__ == "__main__":
    celery_app.start()