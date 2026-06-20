"""
Campaign execution Celery tasks.
"""

import logging
import re
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)


def execute_campaign_async(campaign_id: str):
    """Async campaign execution."""
    import asyncio
    return asyncio.run(_execute_campaign_async(campaign_id))


async def _execute_campaign_async(campaign_id: str) -> dict:
    """Execute a campaign: process pending leads and send emails."""
    from app.config.mongodb_config import get_database
    from app.schemas.email import EmailCreate
    from app.services.email_service import create_email, send_campaign_email
    from app.services.followup_service import create_followup
    from app.utils.id_generator import generate_tracking_id

    db = await get_database()

    campaign = await db.campaigns.find_one({"id": campaign_id})
    if not campaign:
        return {"status": "error", "message": "Campaign not found"}

    if campaign.get("status") != "active":
        return {"status": "skipped", "message": f"Campaign is {campaign.get('status')}"}

    gmail_account_id = campaign.get("gmail_account_id", "")
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

    pipeline = [
        {"$match": {"campaign_id": campaign_id, "status": "new"}},
        {"$limit": campaign.get("daily_send_limit", 50)},
    ]
    leads = await db.leads.aggregate(pipeline).to_list(length=50)

    if not leads:
        return {"status": "complete", "message": "No pending leads"}

    results = []
    for lead in leads:
        try:
            result = await _process_lead(campaign, lead)
            results.append({"lead_id": lead["id"], "status": result})
        except Exception as exc:
            logger.exception("Failed to process lead %s: %s", lead["id"], exc)
            results.append({"lead_id": lead["id"], "status": "error", "error": str(exc)})

    return {
        "status": "processed",
        "campaign_id": campaign_id,
        "leads_processed": len(results),
        "results": results,
    }


def _format_template(text: str, lead: dict, lead_name: str, sender_name: str = "", sender_email: str = "") -> str:
    """Replace template placeholders."""
    if not text:
        return ""

    first_name = lead.get("first_name", "") or lead_name
    last_name = lead.get("last_name", "")

    replacements = {
        "name": lead_name,
        "first_name": first_name,
        "last_name": last_name,
        "company": lead.get("company", ""),
        "role": lead.get("title", "") or lead.get("role", ""),
        "title": lead.get("title", "") or lead.get("role", ""),
        "website": lead.get("website", ""),
        "email": lead.get("email", ""),
        "sender_name": sender_name,
        "sender_email": sender_email,
        "sender_title": "Founder & CEO",
    }

    result = text
    for key, value in replacements.items():
        val_str = str(value) if value else ""
        result = re.sub(r"\{\{\s*" + key + r"\s*\}\}", val_str, result, flags=re.IGNORECASE)
        result = result.replace("{" + key + "}", val_str)

    # Replace bracketed/curly placeholders like [Your Name] and [Your Email]
    if sender_name:
        result = re.sub(r"\[Your\s+Name\]", sender_name, result, flags=re.IGNORECASE)
        result = re.sub(r"\[Sender\s+Name\]", sender_name, result, flags=re.IGNORECASE)
    if sender_email:
        result = re.sub(r"\[Your\s+Email\]", sender_email, result, flags=re.IGNORECASE)
        result = re.sub(r"\[Sender\s+Email\]", sender_email, result, flags=re.IGNORECASE)
    
    result = re.sub(r"\[Your\s+Title\]", "Founder & CEO", result, flags=re.IGNORECASE)
    result = re.sub(r"\[Sender\s+Title\]", "Founder & CEO", result, flags=re.IGNORECASE)
    result = re.sub(r"\{\{\s*sender_title\s*\}\}", "Founder & CEO", result, flags=re.IGNORECASE)

    return result


def convert_text_to_html(text: str) -> str:
    """Convert plain text newlines and markdown formatting to HTML."""
    if not text:
        return ""

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


async def _process_lead(campaign: dict, lead: dict) -> str:
    """Process a single lead: research → personalize → generate → send → schedule follow-ups."""
    from app.config.settings import settings
    from app.config.mongodb_config import get_database
    from app.schemas.email import EmailCreate
    from app.services.email_service import create_email, send_campaign_email
    from app.services.followup_service import create_followup
    from app.utils.id_generator import generate_tracking_id

    db = await get_database()
    user_id = campaign["user_id"]
    gmail_account_id = campaign.get("gmail_account_id", "")

    if not gmail_account_id:
        return "skipped"

    # Fetch sender details for personalization
    user = await db.users.find_one({"id": user_id})
    user_name = user.get("name", "") if user else ""
    user_email = user.get("email", "") if user else ""

    gmail_account = await db.gmail_accounts.find_one({"id": gmail_account_id})
    sender_name = gmail_account.get("name", user_name) if gmail_account else user_name
    sender_email = gmail_account.get("email", user_email) if gmail_account else user_email

    existing_email = await db.emails.find_one({
        "campaign_id": campaign["id"],
        "lead_id": lead["id"],
        "sequence_number": 1,
    })
    if existing_email:
        return "already_sent"

    has_groq = bool(settings.GROQ_API_KEY and settings.GROQ_API_KEY.strip())

    subject = ""
    body_html = ""

    lead_name = f"{lead.get('first_name', '')} {lead.get('last_name', '')}".strip() or lead.get('name', '') or lead.get('email', '')
    lead_data_for_ai = {
        "name": lead_name,
        "email": lead.get("email", ""),
        "company": lead.get("company", ""),
        "role": lead.get("title", "") or lead.get("role", ""),
        "website": lead.get("website", ""),
    }

    if has_groq:
        try:
            import asyncio
            from app.agents.research_agent import research_lead
            from app.agents.personalization_agent import personalize_for_lead
            from app.agents.outreach_writer_agent import write_outreach_email

            research_data = await asyncio.to_thread(research_lead, lead_data_for_ai)
            personalization_data = await asyncio.to_thread(personalize_for_lead, lead_data_for_ai, research_data)
            tone = campaign.get("settings", {}).get("tone", "professional") if isinstance(campaign.get("settings"), dict) else "professional"
            email_content = await asyncio.to_thread(
                write_outreach_email,
                lead_data_for_ai,
                personalization_data,
                tone,
                campaign.get("subject_template", ""),
                campaign.get("body_template", ""),
                sender_name,
                sender_email,
            )

            subject = email_content.get("subject", "")
            body_html = email_content.get("body_html", "")
        except Exception as exc:
            logger.warning("AI email generation failed for lead %s: %s", lead["id"], exc)
            has_groq = False

    if not has_groq or not subject or not body_html:
        subject_tpl = campaign.get("subject_template", "")
        body_tpl = campaign.get("body_template", "")

        subject = _format_template(subject_tpl, lead, lead_name, sender_name, sender_email)
        body_html = _format_template(body_tpl, lead, lead_name, sender_name, sender_email)

    if not subject or not body_html:
        return "skipped"

    # Convert plain text newlines and markdown formatting to HTML
    body_html = convert_text_to_html(body_html)

    tracking_id = generate_tracking_id()

    email_data = EmailCreate(
        campaign_id=campaign["id"],
        lead_id=lead["id"],
        gmail_account_id=gmail_account_id,
        to=lead["email"],
        subject=subject,
        body_html=body_html,
        sequence_number=1,
    )

    email_doc = await create_email(user_id, email_data, tracking_id)
    await send_campaign_email(email_doc["id"])

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