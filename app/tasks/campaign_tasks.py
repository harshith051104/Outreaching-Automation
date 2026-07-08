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
            # Atomically claim lead to prevent duplicate scheduler runs
            updated_lead = await db.leads.find_one_and_update(
                {"_id": lead["_id"], "status": "new"},
                {"$set": {"status": "contacted", "updated_at": datetime.now(timezone.utc)}}
            )
            if not updated_lead:
                logger.info("Scheduler: Lead %s is already being scheduled by another process. Skipping.", lead.get("id"))
                continue

            if campaign.get("sequence_steps"):
                from app.services.task_scheduler_service import TaskSchedulerService
                
                # Prepend the main email template (Initial Campaign Email) as Step 1 (delay 0)
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
                    steps = []
                    for idx, step in enumerate(email_only_steps):
                        steps.append({
                            "step_number": idx + 1,
                            "channel": "email",
                            "delay_days": step.get("delay_days") or 0,
                            "subject_template": step.get("subject_template") or "",
                            "body_template": step.get("body_template") or ""
                        })
                
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
            else:
                result = await _process_lead(campaign, lead)
                results.append({"lead_id": lead["id"], "status": result})
        except Exception as exc:
            logger.exception("Failed to process lead %s: %s", lead["id"], exc)
            results.append({"lead_id": lead["id"], "status": "error", "error": str(exc)})

    # Immediately process delay-0 tasks so first email goes out right away
    # (not waiting up to 30s for celery beat to trigger)
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


def _format_template(text: str, lead: dict, lead_name: str, sender_name: str = "", sender_email: str = "") -> str:
    """Replace template placeholders. Returns unresolved placeholders for AI generation."""
    if not text:
        return ""

    first_name = lead.get("first_name", "") or lead_name
    last_name = lead.get("last_name", "")

    replacements = {
        "name": lead_name,
        "first_name": first_name,
        "last_name": last_name,
        "investor_name": lead_name,
        "investor name": lead_name,
        "company": lead.get("company", ""),
        "role": lead.get("title") or lead.get("role") or "",
        "title": lead.get("title") or lead.get("role") or "",
        "job_title": lead.get("title") or lead.get("role") or "",
        "job title": lead.get("title") or lead.get("role") or "",
        "focus": lead.get("focus", ""),
        "investor_focus": lead.get("focus", ""),
        "status": lead.get("status", ""),
        "score": str(lead.get("score", 0.0)),
        "quality": str(lead.get("lead_quality_score", 0.0)),
        "lead_quality_score": str(lead.get("lead_quality_score", 0.0)),
        "website": lead.get("website", ""),
        "email": lead.get("email", ""),
        "linkedin": lead.get("linkedin", ""),
        "linkedin_url": lead.get("linkedin", ""),
        "linkedin url": lead.get("linkedin", ""),
        "notes": lead.get("notes", ""),
        "sender_name": sender_name,
        "sender_email": sender_email,
        "sender_title": "Founder & CEO",
    }

    result = text
    for key, value in replacements.items():
        val_str = str(value) if value else ""
        result = re.sub(r"\{\{\s*" + key + r"\s*\}\}", val_str, result, flags=re.IGNORECASE)
        result = result.replace("{" + key + "}", val_str)

    # Format custom fields using raw column headings and various normalized forms
    custom_fields = lead.get("custom_fields") or {}
    for k, v in custom_fields.items():
        val_str = str(v) if v else ""
        key_raw = k.strip()
        key_underscore = key_raw.lower().replace(" ", "_")
        key_spaced = key_raw.lower().replace("_", " ")
        key_flat = key_raw.lower().replace(" ", "").replace("_", "")
        
        for placeholder_key in list({key_raw, key_raw.lower(), key_underscore, key_spaced, key_flat}):
            if not placeholder_key:
                continue
            # Double braces replacement (case-insensitive)
            pattern_double = r"\{\{\s*" + re.escape(placeholder_key) + r"\s*\}\}"
            result = re.sub(pattern_double, val_str, result, flags=re.IGNORECASE)
            
            # Single braces replacement (case-insensitive)
            pattern_single = r"\{\s*" + re.escape(placeholder_key) + r"\s*\}"
            result = re.sub(pattern_single, val_str, result, flags=re.IGNORECASE)

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

    # Bracket-style investor placeholders
    investor_name_bracket = lead.get("name", lead_name)
    if investor_name_bracket:
        result = re.sub(r"\[Investor\s+Name\]", investor_name_bracket, result, flags=re.IGNORECASE)
        result = re.sub(r"\[Investors?\s+Name\]", investor_name_bracket, result, flags=re.IGNORECASE)

    # Focus placeholders
    focus_val = lead.get("focus", "") or ""
    if focus_val:
        focus_items = [f.strip() for f in focus_val.split(",") if f.strip()]
        if len(focus_items) <= 2:
            # 1-2 focus areas: use as-is
            combined_focus = ", ".join(focus_items)
            result = re.sub(r"\[Investor\s+Focus\s+Area\]", combined_focus, result, flags=re.IGNORECASE)
            result = re.sub(r"\[Investor\s+Focus\s+1\]", focus_items[0], result, flags=re.IGNORECASE)
            if len(focus_items) > 1:
                result = re.sub(r"\[Investor\s+Focus\s+2\]", focus_items[1], result, flags=re.IGNORECASE)
        # 3+ focus areas: leave [Investor Focus Area] for AI to select most relevant

    # Firm name placeholders
    company_val = lead.get("company", "") or ""
    if company_val:
        result = re.sub(r"\[Firm\s+Name\]", company_val, result, flags=re.IGNORECASE)

    return result


def _extract_unresolved_placeholders(text: str) -> list:
    """Extract remaining {{placeholder}} and [placeholder] patterns from text."""
    double = re.findall(r"\{\{([^}]+)\}\}", text)
    bracket = re.findall(r"\[([^\]]+)\]", text)
    return double + bracket


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
    """Use LLM to generate values for unresolved placeholders in text.
    Uses per-lead+campaign cache to avoid regenerating the same values."""
    unresolved = _extract_unresolved_placeholders(text)
    if not unresolved:
        return text

    # Filter out already-known bracket values like [Investor Name] that are just literal text
    unresolved = [p for p in unresolved if not p.startswith("Investor Name") and len(p) > 2]

    if not unresolved:
        return text

    # Load cached values
    campaign_id = campaign.get("id", "")
    lead_id = lead.get("id", "")
    cached = await _load_cached_placeholders(campaign_id, lead_id) if campaign_id and lead_id else {}

    # Apply cached values first
    for ph in unresolved:
        if ph in cached:
            val_str = cached[ph]
            text = re.sub(r"\{\{\s*" + re.escape(ph) + r"\s*\}\}", val_str, text, flags=re.IGNORECASE)
            text = re.sub(r"\[\s*" + re.escape(ph) + r"\s*\]", val_str, text, flags=re.IGNORECASE)

    # Resolve known placeholders from lead data before sending to LLM
    focus_val = lead.get("focus", "") or ""
    focus_items = [f.strip() for f in focus_val.split(",") if f.strip()] if focus_val else []
    focus_combined = ", ".join(focus_items[:3]) if focus_items else ""  # max 3 items

    # Extract firm description from custom_fields (CSV import stores it there)
    firm_description = lead.get("custom_fields", {}).get("firm_description", "") or ""

    lead_data_replacements = {
        "Investor Focus 1": focus_items[0] if focus_items else "",
        "Investor Focus 2": focus_items[1] if len(focus_items) > 1 else "",
        "Firm Name": lead.get("company", ""),
        "Investor Name": lead.get("name", ""),
        "Firm Description": firm_description,
    }

    # Investor Focus Area: resolve from lead ONLY if 1-2 focus items (not enough choice for AI)
    # If 3+ items OR no focus data → leave unresolved so LLM handles it
    if 0 < len(focus_items) <= 2:
        lead_data_replacements["Investor Focus Area"] = focus_combined

    for ph_name, replacement in lead_data_replacements.items():
        if replacement:
            text = re.sub(r"\[\s*" + re.escape(ph_name) + r"\s*\]", replacement, text, flags=re.IGNORECASE)
            text = re.sub(r"\{\{\s*" + re.escape(ph_name) + r"\s*\}\}", replacement, text, flags=re.IGNORECASE)

    # Re-check unresolved after applying lead data
    unresolved = _extract_unresolved_placeholders(text)
    unresolved = [p for p in unresolved if not p.startswith("Investor Name") and len(p) > 2]

    if not unresolved:
        return text

    # Only send uncached placeholders to LLM
    placeholder_defs = campaign.get("ai_placeholder_definitions", {})

    from app.services.llm_manager import LLMManager

    focus = lead.get("focus", lead.get("custom_fields", {}).get("Focus", ""))
    company = lead.get("company", lead.get("custom_fields", {}).get("Company", ""))
    firm_description = lead.get("custom_fields", {}).get("firm_description", "")

    # Parse all focus areas
    focus_items = [f.strip() for f in focus.split(",") if f.strip()] if focus else []
    focus_all = ", ".join(focus_items) if focus_items else "Not specified"
    # Pick primary focus (first item) for simple references
    focus_primary = focus_items[0] if focus_items else "Not specified"

    # Research ElectraWireless for accurate content
    electra_research = ""
    try:
        from app.services.tavily_service import TavilyService
        tavily = TavilyService()
        research_results = await tavily.search("ElectraWireless wireless power startup", max_results=3, user_id=lead.get("user_id"))
        if research_results:
            electra_research = "\n".join([r.get("content", "") for r in research_results[:3]])
    except Exception as e:
        logger.warning("Tavily research failed for ElectraWireless: %s", e)

    prompt_parts = []
    for ph in unresolved:
        ph_key = ph.strip().lower().replace(" ", "_").replace("-", "_")
        definition = placeholder_defs.get(ph_key) or placeholder_defs.get(ph, "")
        if definition:
            prompt_parts.append(f"- [{ph}]: {definition}")
        else:
            prompt_parts.append(f"- [{ph}]: Generate a contextually appropriate value. This is a placeholder in a cold investor outreach email for ElectraWireless (wireless power infrastructure startup, $5M seed round).")

    research_section = f"\n\nRESEARCH DATA (use this for accurate ElectraWireless details):\n{electra_research}" if electra_research else ""

    focus_instruction = ""
    if len(focus_items) > 2:
        focus_instruction = f"""
INVESTOR FOCUS AREAS (select the 1-2 MOST relevant to ElectraWireless wireless power infrastructure):
{focus_all}

When generating values for placeholders like [Investor Focus Area] or [Specific Thesis Point]:
- Pick the 1-2 focus areas that best align with wireless power, energy infrastructure, hardware, IoT, smart devices, or related tech
- If none clearly align, pick the closest or most adjacent focus area
- Always connect the selected focus to how ElectraWireless's technology addresses that space"""

    system_msg = f"""You are an AI assistant generating personalized email content for investor outreach.

LEAD CONTEXT:
- Name: {lead_name}
- Company/Firm: {company}
- Firm Description: {firm_description or "Not available"}
- Primary Investment Focus: {focus_primary}
- All Investment Focus Areas: {focus_all}
- Email: {lead.get('email', '')}

CAMPAIGN CONTEXT:
- Product: ElectraWireless - wireless power infrastructure (5W-30kW)
- Strategy: Phased rollout (Smart Kitchens -> Industrial -> EV)
- AI Control Layer: Elly (SaaS revenue)
- Raise: $5M seed round{research_section}{focus_instruction}

Generate ONLY the placeholder values as JSON. Keys are the EXACT placeholder text (without brackets or braces), values are the generated text.
Keep each value concise (1-2 sentences max). Be specific and credible.
Use the RESEARCH DATA when available to ensure accuracy about ElectraWireless.
Return valid JSON dict like: {{"Investor Focus 1": "generated value", "Specific Thesis Point": "generated value"}}

PLACEHOLDERS TO GENERATE:
{chr(10).join(prompt_parts)}"""

    try:
        result = await LLMManager.generate_completion(
            task_type="email_personalization",
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": "Generate the placeholder values."},
            ],
            user_id=lead.get("user_id", "system"),
            temperature=0.7,
        )

        content = result.get("content", "{}")
        import json
        # Try to extract JSON from response
        json_match = re.search(r"\{[^}]+\}", content, re.DOTALL)
        if json_match:
            generated = json.loads(json_match.group())
            # Save to cache for reuse
            if campaign_id and lead_id and generated:
                await _save_cached_placeholders(campaign_id, lead_id, generated)
            for ph, value in generated.items():
                val_str = str(value) if value else ""
                # Replace both {{placeholder}} and [placeholder] forms
                text = re.sub(r"\{\{\s*" + re.escape(ph) + r"\s*\}\}", val_str, text, flags=re.IGNORECASE)
                text = re.sub(r"\[\s*" + re.escape(ph) + r"\s*\]", val_str, text, flags=re.IGNORECASE)
    except Exception as exc:
        logger.error("AI placeholder generation failed: %s", exc)

    return text


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

    lead_email = lead.get("email", "").strip()
    if not lead_email:
        logger.warning("Email task skipped for lead %s — no email address found.", lead.get("id"))
        return "skipped"

    lead_name = f"{lead.get('first_name', '')} {lead.get('last_name', '')}".strip() or lead.get('name', '') or lead_email
    lead_data_for_ai = {
        "name": lead_name,
        "email": lead_email,
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
                "",  # sender_title
                campaign.get("description", ""),
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

        # AI-generate any remaining unresolved placeholders
        subject = await _ai_generate_placeholders(subject, lead, campaign, lead_name, sender_name)
        body_html = await _ai_generate_placeholders(body_html, lead, campaign, lead_name, sender_name)

    if not subject or not body_html:
        return "skipped"

    # Convert plain text newlines and markdown formatting to HTML
    body_html = convert_text_to_html(body_html)

    tracking_id = generate_tracking_id()

    # Run AI review guardrails before sending
    from app.services.guardrail_service import run_guardrail_review
    guardrail_report = await run_guardrail_review(subject, body_html, user_id)

    email_data = EmailCreate(
        campaign_id=campaign["id"],
        lead_id=lead["id"],
        gmail_account_id=gmail_account_id,
        to=lead_email,
        subject=subject,
        body_html=body_html,
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
    logger.info("Email sent to %s for lead %s", lead_email, lead_name)

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
                    # Rollback status to new
                    await db.leads.update_one(
                        {"_id": lead["_id"]},
                        {"$set": {"status": "new", "updated_at": datetime.now(timezone.utc)}}
                    )
                
    return {"status": "ok", "scheduled_leads": scheduled_count}


@celery_app.task(name="app.tasks.campaign_tasks.process_scheduled_campaign_tasks")
def process_scheduled_campaign_tasks_task():
    """Celery task wrapper to process scheduled campaign tasks."""
    import asyncio
    from app.services.task_scheduler_service import TaskSchedulerService
    
    logger.info("Celery Task: Processing scheduled campaign tasks...")
    
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    loop.run_until_complete(TaskSchedulerService.process_pending_tasks())
    logger.info("Celery Task: Scheduled campaign tasks processing completed.")
    return {"status": "ok"}