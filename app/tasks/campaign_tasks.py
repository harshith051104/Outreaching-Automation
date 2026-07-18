"""
Campaign execution Celery tasks.

Refactored to use the campaigns/ modular runtime.
Maintains backward compatibility with existing FastAPI routes, MongoDB schemas,
Celery workers, Gmail integration, and campaign execution flow.
"""

import sys
import os

# Ensure project root is in sys.path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    import campaigns
    print(f"\n📦 [CAMPAIGN_TASKS IMPORT] campaigns module imported from: {campaigns.__file__}\n")
except Exception as e:
    print(f"\n❌ [CAMPAIGN_TASKS IMPORT] Failed to import campaigns: {e}\n")

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def execute_campaign_async(campaign_id: str):
    """Async campaign execution."""
    import asyncio
    return asyncio.run(_execute_campaign_async(campaign_id))


async def _execute_campaign_async(campaign_id: str) -> dict:
    """Execute a campaign: process pending leads and send emails."""
    from app.config.mongodb_config import get_database
    from campaigns.runtime import CampaignRuntime

    db = await get_database()

    campaign = await db.campaigns.find_one({"id": campaign_id})
    if not campaign:
        return {"status": "error", "message": "Campaign not found"}

    if campaign.get("status") != "active":
        return {"status": "skipped", "message": f"Campaign is {campaign.get('status')}"}

    gmail_account_id = campaign.get("gmail_account_id", "")
    if gmail_account_id:
        gmail_acct = await db.gmail_accounts.find_one({"id": gmail_account_id, "is_active": True})
        if not gmail_acct:
            gmail_account_id = ""

    if not gmail_account_id:
        account = await db.gmail_accounts.find_one({"user_id": campaign["user_id"], "is_active": True})
        if account:
            gmail_account_id = account["id"]
            await db.campaigns.update_one(
                {"id": campaign["id"]},
                {"$set": {"gmail_account_id": gmail_account_id}},
            )

    if not gmail_account_id:
        return {"status": "error", "message": "No Gmail account connected"}

    campaign["gmail_account_id"] = gmail_account_id

    # Count how many emails have already been sent today for this Gmail account (or user)
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    query = {
        "status": "sent",
        "sent_at": {"$gte": today_start}
    }
    if gmail_account_id:
        query["gmail_account_id"] = gmail_account_id
    else:
        query["campaign_id"] = campaign_id

    sent_today = await db.emails.count_documents(query)

    daily_limit = campaign.get("daily_send_limit")
    user_id = campaign.get("user_id")
    if user_id:
        prefs = await db.system_settings.find_one({"user_id": user_id, "type": "system_preferences"})
        if prefs and "dailyLimit" in prefs:
            daily_limit = prefs["dailyLimit"]
    if daily_limit is None:
        daily_limit = 50

    remaining = max(0, daily_limit - sent_today)

    if remaining <= 0:
        logger.info("Campaign %s has reached its daily limit of %d emails today. Skipping execution.", campaign_id, daily_limit)
        return {"status": "skipped", "message": "Daily send limit reached"}

    pipeline = [
        {"$match": {"campaign_id": campaign_id, "status": "new"}},
        {"$limit": remaining},
    ]
    leads = await db.leads.aggregate(pipeline).to_list(length=remaining)

    if not leads:
        return {"status": "complete", "message": "No pending leads"}

    runtime = CampaignRuntime(db=db)
    results = []
    for lead in leads:
        try:
            # Atomically claim lead to prevent duplicate scheduler runs
            updated_lead = await db.leads.find_one_and_update(
                {"_id": lead["_id"], "status": "new"},
                {"$set": {"status": "contacted", "updated_at": datetime.now(timezone.utc)}}
            )
            if not updated_lead:
                logger.info("Scheduler: Lead %s is already being scheduled by another process. Skipping.", lead.get("id"))
                continue

            from app.services.task_scheduler_service import TaskSchedulerService

            # Formulate the steps for this lead's sequence
            if campaign.get("subject_template") or campaign.get("body_template"):
                main_email = {
                    "step_number": 1,
                    "channel": "email",
                    "delay_days": 0,
                    "subject_template": campaign.get("subject_template") or "Quick question",
                    "body_template": campaign.get("body_template") or "Hi {{first_name}},"
                }
                steps = [main_email]
                custom_steps = campaign.get("sequence_steps") or []
                email_only_steps = [s for s in custom_steps if s.get("channel", "email").lower() != "linkedin"]
                for idx, step in enumerate(email_only_steps):
                    steps.append({
                        "step_number": idx + 2,
                        "channel": "email",
                        "delay_days": step.get("delay_days") or 0,
                        "subject_template": step.get("subject_template") or "",
                        "body_template": step.get("body_template") or ""
                    })
            else:
                custom_steps = campaign.get("sequence_steps") or []
                email_only_steps = [s for s in custom_steps if s.get("channel", "email").lower() != "linkedin"]
                if email_only_steps:
                    steps = []
                    for idx, step in enumerate(email_only_steps):
                        steps.append({
                            "step_number": idx + 1,
                            "channel": "email",
                            "delay_days": step.get("delay_days") or 0,
                            "subject_template": step.get("subject_template") or "",
                            "body_template": step.get("body_template") or ""
                        })
                else:
                    steps = [
                        {"step_number": 1, "channel": "email", "delay_days": 0,
                         "subject_template": campaign.get("subject_template") or "Quick question",
                         "body_template": campaign.get("body_template") or "Hi {{first_name}},"},
                        {"step_number": 2, "channel": "email", "delay_days": 3,
                         "subject_template": "Re: " + (campaign.get("subject_template") or "Quick question"),
                         "body_template": "Hi {{first_name}},\n\nJust following up on my previous message. Any thoughts?"},
                        {"step_number": 3, "channel": "email", "delay_days": 10,
                         "subject_template": "{{company}} + {{sender_name}}",
                         "body_template": "Hi {{first_name}},\n\nI noticed {{company}} has been growing rapidly. We've helped similar companies achieve great results.\n\nWould love to share how we could help.\n\nBest"},
                        {"step_number": 4, "channel": "email", "delay_days": 20,
                         "subject_template": "One last try",
                         "body_template": "Hi {{first_name}},\n\nI hope this finds you well. I'll respect your time and won't reach out again after this.\n\nBest"}
                    ]

            try:
                await TaskSchedulerService.schedule_lead_sequence(
                    user_id=campaign["user_id"],
                    campaign_id=campaign["id"],
                    lead_id=lead["id"],
                    sequence_steps=steps
                )
                results.append({"lead_id": lead["id"], "status": "scheduled_sequence"})
            except Exception as sched_err:
                # Rollback status to new
                await db.leads.update_one(
                    {"_id": lead["_id"]},
                    {"$set": {"status": "new", "updated_at": datetime.now(timezone.utc)}}
                )
                raise sched_err
        except Exception as exc:
            logger.exception("Failed to process lead %s: %s", lead["id"], exc)
            results.append({"lead_id": lead["id"], "status": "error", "error": str(exc)})

    # Immediately process delay-0 tasks so first email goes out right away
    try:
        from app.services.task_scheduler_service import TaskSchedulerService
        await TaskSchedulerService.process_pending_tasks()
        logger.info("Campaign %s: Triggered immediate processing of delay-0 tasks", campaign_id)
    except Exception as proc_err:
        logger.warning("Campaign %s: Failed to trigger immediate task processing: %s", campaign_id, proc_err)

    return {
        "status": "processed",
        "campaign_id": campaign_id,
        "leads_processed": len(results),
        "results": results,
    }


# ── Backward-compatible wrappers ──────────────────────────────────────────
# These delegate to the campaigns/ modules while preserving the original API.

def _format_template(text: str, lead: dict, lead_name: str, sender_name: str = "", sender_email: str = "") -> str:
    """Backward-compatible template formatting. Delegates to PlaceholderEngine."""
    from campaigns.placeholder_engine import PlaceholderEngine
    from campaigns.artifacts import ResearchArtifact
    from campaigns.research import ResearchEngine

    if not text:
        return ""

    engine = PlaceholderEngine()
    # Build a minimal ResearchArtifact synchronously (no DB calls needed)
    first_name = lead.get("first_name", "").strip()
    last_name = lead.get("last_name", "").strip()
    # Avoid "David Brown Brown" when first_name already holds the full name.
    if last_name and first_name.lower().endswith(last_name.lower()):
        last_name = ""

    if not first_name and lead_name:
        parts = lead_name.strip().split(None, 1)
        first_name = parts[0]
        if not last_name and len(parts) > 1:
            last_name = parts[1]

    research = ResearchArtifact(
        lead_id=lead.get("id", ""),
        campaign_id="",
        investor_name=lead_name,
        first_name=first_name,
        last_name=last_name,
        firm_name=lead.get("company", ""),
        investor_focus=lead.get("focus", ""),
        investor_focus_items=[f.strip() for f in (lead.get("focus") or "").split(",") if f.strip()],
        firm_description=(lead.get("custom_fields") or {}).get("firm_description", ""),
        lead_email=lead.get("email", ""),
        lead_title=lead.get("title") or lead.get("role") or "",
        lead_website=lead.get("website", ""),
        lead_linkedin=lead.get("linkedin", ""),
        custom_fields=lead.get("custom_fields") or {},
        sender_name=sender_name,
        sender_email=sender_email,
        sender_title="Founder & CEO",
    )

    resolved, _ = engine.resolve_all(text, research)
    return resolved


def _extract_unresolved_placeholders(text: str) -> list:
    """Extract remaining {{placeholder}} and [placeholder] patterns from text."""
    double = re.findall(r"\{\{([^}]+)\}\}", text)
    bracket = re.findall(r"\[([^\]]+)\]", text)
    return double + bracket


# LLMs often rename well-known placeholders when returning the JSON map.
_ALIAS_GROUPS = [
    {
        "aivalueprop", "valueprop", "valueproposition", "valueproposal",
        "proposition", "prop", "fit", "benefit", "reason", "proposal",
    },
]
# Build lookup from all alias group members
_ALIAS_LOOKUP = {}
for _group in _ALIAS_GROUPS:
    for _member in _group:
        _ALIAS_LOOKUP[_member] = _group


def _placeholder_alias_match(norm_ph: str, gen_key: str) -> bool:
    """True if a generated JSON key can fill a template placeholder."""
    if norm_ph == gen_key or gen_key in norm_ph or norm_ph in gen_key:
        return True
    # Normalize gen_key for lookup
    norm_gen = gen_key.strip().lower().replace("_", "").replace("-", "").replace(" ", "")
    gp = _ALIAS_LOOKUP.get(norm_ph)
    gg = _ALIAS_LOOKUP.get(norm_gen)
    return gp is not None and gp is gg


async def _load_cached_placeholders(campaign_id: str, lead_id: str) -> dict:
    """Load cached AI-generated placeholder values for a lead+campaign."""
    from app.config.mongodb_config import get_database
    db = await get_database()
    cache_key = f"{campaign_id}:{lead_id}"
    doc = await db.ai_placeholder_cache.find_one({"cache_key": cache_key})
    if doc:
        return doc.get("values", {})
    return {}


async def _save_cached_placeholders(campaign_id: str, lead_id: str, values: dict) -> None:
    """Save AI-generated placeholder values to cache."""
    from app.config.mongodb_config import get_database
    from datetime import datetime, timezone
    db = await get_database()
    cache_key = f"{campaign_id}:{lead_id}"
    await db.ai_placeholder_cache.update_one(
        {"cache_key": cache_key},
        {"$set": {"values": values, "updated_at": datetime.now(timezone.utc)}},
        upsert=True,
    )


async def _clear_cached_placeholders(campaign_id: str, lead_id: str) -> None:
    """Clear cached AI placeholder values for a lead+campaign (for regeneration)."""
    from app.config.mongodb_config import get_database
    db = await get_database()
    cache_key = f"{campaign_id}:{lead_id}"
    await db.ai_placeholder_cache.delete_one({"cache_key": cache_key})


async def _ai_generate_placeholders(
    text: str,
    lead: dict,
    campaign: dict,
    lead_name: str,
    sender_name: str = "",
) -> str:
    """Backward-compatible AI placeholder generation. Delegates to PersonalizationEngine."""
    from campaigns.personalization import PersonalizationEngine
    from campaigns.placeholder_engine import PlaceholderEngine
    from campaigns.research import ResearchEngine
    from campaigns.artifacts import ResearchArtifact
    from app.services.llm_manager import LLMManager

    # Normalize non-breaking spaces
    text = text.replace("\xa0", " ").replace("&nbsp;", " ")

    # Build ResearchArtifact from lead data
    focus_val = lead.get("focus", "") or ""
    focus_items = [f.strip() for f in focus_val.split(",") if f.strip()]

    # Handle name doubling: if first_name already ends with last_name, clear last_name
    first_name = lead.get("first_name", "").strip()
    last_name = lead.get("last_name", "").strip()
    if last_name and first_name.lower().endswith(last_name.lower()):
        last_name = ""

    # Pick best focus for single-slot placeholders
    ELECTRA_KEYWORDS = [
        "wireless", "iot", "internet of things", "energy", "power", "hardware",
        "ai", "artificial intelligence", "automation", "b2b", "saas", "infrastructure",
        "deep tech", "deeptech", "semiconductor", "robotics", "smart", "manufacturing",
        "industrial", "finance", "fintech", "climate", "clean", "electrification",
        "mobility", "ev", "logistics", "developer", "cloud", "cybersecurity",
    ]
    best_focus = focus_items[0] if focus_items else ""
    for fi in focus_items:
        if any(kw in fi.lower() for kw in ELECTRA_KEYWORDS):
            best_focus = fi
            break

    # Resolve known lead data placeholders locally first
    firm_description = (lead.get("custom_fields") or {}).get("firm_description", "")
    lead_data_replacements = {
        "Investor Focus 1": focus_items[0] if focus_items else "",
        "Investor Focus 2": focus_items[1] if len(focus_items) > 1 else "",
        "Firm Name": lead.get("company", ""),
        "Investor Name": lead.get("name", ""),
        "Firm Description": firm_description,
        "last_name": last_name,
        "first_name": first_name,
        "focus": focus_val,
        "investor_focus": focus_val,
    }
    # Investor Focus Area: resolve from lead if 1-2 focus items
    if 0 < len(focus_items) <= 2:
        lead_data_replacements["Investor Focus Area"] = ", ".join(focus_items[:3])

    for ph_name, replacement in lead_data_replacements.items():
        if replacement or ph_name in ("last_name", "first_name"):
            text = re.sub(r"\[\s*" + re.escape(ph_name) + r"\s*\]", replacement or "", text, flags=re.IGNORECASE)
            text = re.sub(r"\{\{\s*" + re.escape(ph_name) + r"\s*\}\}", replacement or "", text, flags=re.IGNORECASE)

    # Recheck unresolved after applying lead data
    unresolved = _extract_unresolved_placeholders(text)
    if not unresolved:
        return text

    unresolved = [p for p in unresolved if not p.lower().startswith("investor name") and len(p) > 2]
    if not unresolved:
        return text

    research = ResearchArtifact(
        lead_id=lead.get("id", ""),
        campaign_id=campaign.get("id", ""),
        investor_name=lead_name,
        first_name=first_name,
        last_name=last_name,
        firm_name=lead.get("company", ""),
        investor_focus=focus_items[0] if focus_items else "",
        investor_focus_items=focus_items,
        firm_description=(lead.get("custom_fields") or {}).get("firm_description", ""),
        lead_email=lead.get("email", ""),
        lead_title=lead.get("title") or lead.get("role") or "",
        custom_fields=lead.get("custom_fields") or {},
        sender_name=sender_name,
        sender_email=lead.get("email", ""),
        sender_title="Founder & CEO",
    )

    engine = PersonalizationEngine(llm_manager=LLMManager)
    artifact = await engine.generate(research, unresolved)

    # Apply generated values to text
    if artifact.ai_value_prop:
        for ph in unresolved:
            norm = ph.lower().replace(" ", "_").replace("-", "_")
            if norm in ("ai_value_prop", "aivalueprop", "value_prop", "valueprop",
                        "value_proposition", "valueproposition", "proposition", "prop"):
                text = re.sub(r"\{\{\s*" + re.escape(ph) + r"\s*\}\}", artifact.ai_value_prop, text, flags=re.IGNORECASE)
                text = re.sub(r"\[\s*" + re.escape(ph) + r"\s*\]", artifact.ai_value_prop, text, flags=re.IGNORECASE)
                break

    # Apply custom AI fields
    for key, val in artifact.custom_ai_fields.items():
        if val:
            text = re.sub(r"\{\{\s*" + re.escape(key) + r"\s*\}\}", val, text, flags=re.IGNORECASE)
            text = re.sub(r"\[\s*" + re.escape(key) + r"\s*\]", val, text, flags=re.IGNORECASE)

    # Cache the generated values
    campaign_id = campaign.get("id", "")
    lead_id = lead.get("id", "")
    if campaign_id and lead_id and (artifact.ai_value_prop or artifact.custom_ai_fields):
        cache_vals = {}
        if artifact.ai_value_prop:
            cache_vals["ai_value_prop"] = artifact.ai_value_prop
        cache_vals.update(artifact.custom_ai_fields)
        await _save_cached_placeholders(campaign_id, lead_id, cache_vals)

    # Verify no unresolved remain
    unresolved_after = _extract_unresolved_placeholders(text)
    unresolved_after = [p for p in unresolved_after if not p.startswith("Investor Name") and len(p.strip()) > 2]
    if unresolved_after:
        raise RuntimeError(f"Email contains unresolved placeholders after generation: {unresolved_after}")

    return text


def strip_inline_colors(html_text: str) -> str:
    """Strip inline text colors and backgrounds from HTML styles to prevent light-on-white text issues."""
    if not html_text:
        return ""

    def clean_style_match(match):
        style_content = match.group(2)
        style_content = re.sub(r'(?i)color\s*:\s*[^;"]+;?', '', style_content)
        style_content = re.sub(r'(?i)background-color\s*:\s*[^;"]+;?', '', style_content)
        style_content = re.sub(r'(?i)background\s*:\s*[^;"]+;?', '', style_content)
        style_content = style_content.strip().strip(';').strip()
        if style_content:
            return f'{match.group(1)}="{style_content}"'
        else:
            return ''

    # Clean style="..." attributes
    cleaned = re.sub(r'(style)\s*=\s*"([^"]*)"', clean_style_match, html_text)
    # Clean style='...' attributes
    cleaned = re.sub(r"(style)\s*=\s*'([^']*)'", clean_style_match, cleaned)
    return cleaned


def convert_text_to_html(text: str) -> str:
    """Convert plain text newlines and markdown formatting to HTML."""
    if not text:
        return ""

    # Normalize non-breaking spaces
    text = text.replace("\xa0", " ").replace("&nbsp;", " ")
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    has_html = any(tag in text.lower() for tag in ["<p>", "<br", "<div>", "<span>", "<strong>", "<b>", "<em>", "<i>", "<u>", "<p ", "<a "])

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

    return strip_inline_colors(text)


async def _process_lead(campaign: dict, lead: dict) -> str:
    """Process a single lead: research -> personalize -> generate -> send -> schedule follow-ups."""
    from app.config.settings import settings
    from app.config.mongodb_config import get_database
    from app.schemas.email import EmailCreate
    from app.services.email_service import create_email, send_campaign_email
    from app.services.followup_service import create_followup
    from app.utils.id_generator import generate_tracking_id
    from campaigns.runtime import CampaignRuntime

    db = await get_database()
    user_id = campaign["user_id"]
    gmail_account_id = campaign.get("gmail_account_id", "")

    if not gmail_account_id:
        return "skipped"

    # Fetch sender details for personalization
    user = await db.users.find_one({"id": user_id})
    gmail_account = await db.gmail_accounts.find_one({"id": gmail_account_id})

    existing_email = await db.emails.find_one({
        "campaign_id": campaign["id"],
        "lead_id": lead["id"],
        "sequence_number": 1,
    })
    if existing_email:
        return "already_sent"

    lead_email = lead.get("email", "").strip()
    if not lead_email:
        logger.warning("Email task skipped for lead %s — no email address found.", lead.get("id"))
        return "skipped"

    subject_tpl = campaign.get("subject_template", "")
    body_tpl = campaign.get("body_template", "")

    if not subject_tpl and not body_tpl:
        return "skipped"

    # Use CampaignRuntime for the full compilation pipeline
    runtime = CampaignRuntime(db=db)
    artifact = await runtime.compile_lead_email(lead, campaign, user, gmail_account)

    # Validate
    if not artifact.validation.get("passed", False):
        logger.warning("Email validation failed for lead %s: %s", lead["id"], artifact.validation.get("issues"))
        return "validation_failed"

    if not artifact.subject or not artifact.body:
        return "skipped"

    # Run AI review guardrails before sending
    from app.services.guardrail_service import run_guardrail_review
    guardrail_report = await run_guardrail_review(artifact.subject, artifact.body, user_id)

    tracking_id = generate_tracking_id()
    email_data = EmailCreate(
        campaign_id=campaign["id"],
        lead_id=lead["id"],
        gmail_account_id=gmail_account_id,
        to=lead_email,
        subject=artifact.subject,
        body_html=artifact.body,
        sequence_number=1,
        guardrail=guardrail_report,
    )

    email_doc = await create_email(user_id, email_data, tracking_id)

    if not guardrail_report.get("passed", True):
        logger.warning(f"Email task for lead {lead['id']} blocked by AI Guardrails (Score: {guardrail_report.get('score')})")
        await db.emails.update_one(
            {"id": email_doc["id"]},
            {"$set": {"status": "failed_guardrail", "updated_at": datetime.now(timezone.utc)}}
        )
        from app.services.outreach_tracker_service import log_timeline_event
        await log_timeline_event(
            lead_id=lead["id"],
            user_id=user_id,
            event_type="note_added",
            description=f"AI email blocked by Guardrails (Score: {guardrail_report.get('score')}/100). Comments: {guardrail_report.get('comments')}",
            campaign_id=campaign["id"]
        )
        return "failed"

    await send_campaign_email(email_doc["id"])
    logger.info("Email sent to %s for lead %s", lead_email, lead.get("name", ""))

    await db.leads.update_one(
        {"id": lead["id"]},
        {"$set": {"status": "contacted", "updated_at": datetime.now(timezone.utc)}},
    )

    # Only schedule follow-ups if followup_enabled is explicitly true AND there are no sequence steps configured in the flow
    if campaign.get("followup_enabled", False) and not campaign.get("sequence_steps"):
        followup_stages = campaign.get("followup_stages", 3)
        for seq in range(2, followup_stages + 2):
            delay_hours = campaign.get("followup_delay_days", 3) * 24 * seq
            scheduled_at = datetime.now(timezone.utc) + timedelta(hours=delay_hours)
            await create_followup(
                email_id=email_doc["id"],
                campaign_id=campaign["id"],
                lead_id=lead["id"],
                user_id=user_id,
                sequence_number=seq,
                scheduled_at=scheduled_at,
            )

    return "sent"


from app.config.redis_config import celery_app

@celery_app.task(name="app.tasks.campaign_tasks.process_active_campaigns")
def process_active_campaigns_task():
    """Celery task wrapper to find active campaigns and schedule sequences for new leads."""
    import sys
    import os
    # Ensure project root is in sys.path inside worker process context
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
        
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(_process_active_campaigns_async())


async def _process_active_campaigns_async() -> dict:
    from app.config.mongodb_config import get_database
    from app.services.task_scheduler_service import TaskSchedulerService

    db = await get_database()
    now = datetime.now(timezone.utc)

    active_campaigns = await db.campaigns.find({"status": "active"}).to_list(length=100)
    scheduled_count = 0

    for campaign in active_campaigns:
        pending_leads = await db.leads.find({
            "campaign_id": campaign["id"],
            "status": "new"
        }).to_list(length=50)

        if pending_leads:
            logger.info("Celery Scheduler: Scheduling sequences for %d new leads in campaign '%s'",
                        len(pending_leads), campaign.get("name"))

            if campaign.get("subject_template") or campaign.get("body_template"):
                main_email = {
                    "step_number": 1,
                    "channel": "email",
                    "delay_days": 0,
                    "subject_template": campaign.get("subject_template") or "Quick question",
                    "body_template": campaign.get("body_template") or "Hi {{first_name}},"
                }
                steps = [main_email]
                custom_steps = campaign.get("sequence_steps") or []
                email_only_steps = [s for s in custom_steps if s.get("channel", "email").lower() != "linkedin"]
                for idx, step in enumerate(email_only_steps):
                    steps.append({
                        "step_number": idx + 2,
                        "channel": "email",
                        "delay_days": step.get("delay_days") or 0,
                        "subject_template": step.get("subject_template") or "",
                        "body_template": step.get("body_template") or ""
                    })
            else:
                custom_steps = campaign.get("sequence_steps") or []
                email_only_steps = [s for s in custom_steps if s.get("channel", "email").lower() != "linkedin"]
                if email_only_steps:
                    steps = []
                    for idx, step in enumerate(email_only_steps):
                        steps.append({
                            "step_number": idx + 1,
                            "channel": "email",
                            "delay_days": step.get("delay_days") or 0,
                            "subject_template": step.get("subject_template") or "",
                            "body_template": step.get("body_template") or ""
                        })
                else:
                    steps = [
                        {"step_number": 1, "channel": "email", "delay_days": 0,
                         "subject_template": campaign.get("subject_template") or "Quick question",
                         "body_template": campaign.get("body_template") or "Hi {{first_name}},"},
                        {"step_number": 2, "channel": "email", "delay_days": 3,
                         "subject_template": "Re: " + (campaign.get("subject_template") or "Quick question"),
                         "body_template": "Hi {{first_name}},\n\nJust following up on my previous message. Any thoughts?"},
                        {"step_number": 3, "channel": "email", "delay_days": 10,
                         "subject_template": "{{company}} + {{sender_name}}",
                         "body_template": "Hi {{first_name}},\n\nI noticed {{company}} has been growing rapidly. We've helped similar companies achieve great results.\n\nWould love to share how we could help.\n\nBest"},
                        {"step_number": 4, "channel": "email", "delay_days": 20,
                         "subject_template": "One last try",
                         "body_template": "Hi {{first_name}},\n\nI hope this finds you well. I'll respect your time and won't reach out again after this.\n\nBest"}
                    ]

            for lead in pending_leads:
                lead_id = lead.get("id") or str(lead["_id"])

                # Atomically claim lead to prevent duplicate scheduler runs
                updated_lead = await db.leads.find_one_and_update(
                    {"_id": lead["_id"], "status": "new"},
                    {"$set": {"status": "contacted", "updated_at": now}}
                )
                if not updated_lead:
                    logger.info("Celery Scheduler: Lead %s is already being scheduled by another process. Skipping.", lead_id)
                    continue

                try:
                    await TaskSchedulerService.schedule_lead_sequence(
                        user_id=campaign["user_id"],
                        campaign_id=campaign["id"],
                        lead_id=lead_id,
                        sequence_steps=steps
                    )
                    scheduled_count += 1
                except Exception as lead_exc:
                    logger.error("Celery Scheduler: FAILED to schedule lead %s (%s): %s", lead_id, lead.get("email"), lead_exc)
                    await db.leads.update_one(
                        {"_id": lead["_id"]},
                        {"$set": {"status": "new", "updated_at": datetime.now(timezone.utc)}}
                    )

    return {"status": "ok", "scheduled_leads": scheduled_count}


@celery_app.task(name="app.tasks.campaign_tasks.process_scheduled_campaign_tasks")
def process_scheduled_campaign_tasks_task():
    """Celery task wrapper to process scheduled campaign tasks."""
    import asyncio
    import sys
    import os
    
    # Ensure project root is in sys.path inside worker process context
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
        
    from app.services.task_scheduler_service import TaskSchedulerService

    logger.info("Celery Task: Processing scheduled campaign tasks...")
    logger.info("Celery Task CWD: %s", os.getcwd())
    logger.info("Celery Task sys.path: %s", sys.path)

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    loop.run_until_complete(TaskSchedulerService.process_pending_tasks())
    logger.info("Celery Task: Scheduled campaign tasks processing completed.")
    return {"status": "ok"}
