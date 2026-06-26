"""
Chatbot Service Layer.

Utilises the Groq LLM to interpret user prompts and execute platform
automations via native tool calling. Provides 20+ tools covering
campaign management, lead operations, email handling, analytics,
and sender account management.

Inspired by the fastmcp_instantlyai workflow but using native backend.
"""

import json
import logging
import re
from typing import Any, List, Dict
from datetime import datetime, timezone

from groq import Groq

from app.config.settings import settings
from app.config.groq_config import llm_chat_completion
from app.config.mongodb_config import get_database
from app.services.campaign_service import (
    create_campaign,
    get_campaigns,
    start_campaign,
    pause_campaign,
    get_campaign_stats,
)
from app.services.lead_service import (
    create_lead,
    get_leads,
)
from app.schemas.campaign import CampaignCreate, CampaignSettings
from app.schemas.lead import LeadCreate

logger = logging.getLogger(__name__)

# Initialize Groq client
try:
    groq_client = Groq(api_key=settings.GROQ_API_KEY) if settings.GROQ_API_KEY else None
except Exception as e:
    logger.warning(f"Failed to initialize Groq client: {e}")
    groq_client = None


def _validate_email(email: str) -> bool:
    """Check if a string looks like a valid email address."""
    return bool(re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email.strip()))


def _is_uuid(s: str) -> bool:
    """Check if a string looks like a UUID."""
    return bool(re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', s, re.IGNORECASE))


async def _resolve_campaign_id(campaign_id: str, user_id: str, db) -> str:
    """Resolve a campaign name or alias to the database campaign ID."""
    if not campaign_id:
        return ""
    campaign_id_str = str(campaign_id).strip()
    if not campaign_id_str:
        return ""
    if _is_uuid(campaign_id_str):
        return campaign_id_str
    # Search by name case-insensitively
    campaign = await db.campaigns.find_one({
        "name": {"$regex": f"^{re.escape(campaign_id_str)}$", "$options": "i"},
        "user_id": user_id
    })
    if campaign:
        return campaign["id"]
    return campaign_id_str



async def _resolve_message_templates(msg: str, user_id: str) -> str:
    """Resolve {{sender_name}} and remove {{sender_email}} templates from direct messages."""
    if not msg:
        return msg
    from app.config.mongodb_config import get_database
    db = await get_database()
    
    # Try to resolve user_name from the active LinkedIn session first
    user_name = ""
    session = await db.linkedin_sessions.find_one({"user_id": user_id})
    if session and session.get("account_name"):
        user_name = session.get("account_name")
        
    if not user_name:
        user = await db.users.find_one({"id": user_id})
        user_name = user.get("name", "") if user else ""
    
    # Replace sender name templates
    msg = re.sub(r"\{\{\s*sender_name\s*\}\}", user_name, msg, flags=re.IGNORECASE)
    msg = re.sub(r"\[Your\s+Name\]", user_name, msg, flags=re.IGNORECASE)
    msg = re.sub(r"\[Sender\s+Name\]", user_name, msg, flags=re.IGNORECASE)
    
    # Filter out lines that only contain email template placeholders (to leave no empty lines)
    lines = msg.splitlines()
    filtered_lines = []
    for line in lines:
        if re.match(r"^\s*\{\{\s*sender_email\s*\}\}\s*$", line, re.IGNORECASE):
            continue
        if re.match(r"^\s*\[Your\s+Email\]\s*$", line, re.IGNORECASE):
            continue
        if re.match(r"^\s*\[Sender\s+Email\]\s*$", line, re.IGNORECASE):
            continue
        filtered_lines.append(line)
    msg = "\n".join(filtered_lines)
    
    # General fallback for inline occurrences
    msg = re.sub(r"\{\{\s*sender_email\s*\}\}", "", msg, flags=re.IGNORECASE)
    msg = re.sub(r"\[Your\s+Email\]", "", msg, flags=re.IGNORECASE)
    msg = re.sub(r"\[Sender\s+Email\]", "", msg, flags=re.IGNORECASE)
    
    return msg.strip()


async def _generate_ai_outreach_message(user_id: str, lead: dict) -> str:
    from app.config.groq_config import get_groq_client
    from app.config.settings import settings
    
    lead_name = lead.get("name", "there")
    company = lead.get("company", "your company")
    focus = lead.get("focus", "")
    
    system_prompt = (
        "You are an expert sales outreach assistant generating a LinkedIn first connection message. "
        "Create a short, engaging, and professional first outreach message to the lead. "
        "Keep it under 300 characters, and do NOT use generic placeholders or emojis."
    )
    user_prompt = f"Lead Name: {lead_name}\nCompany: {company}\nFocus: {focus}\nGenerate the message."
    
    try:
        client = get_groq_client(user_id)
        model = getattr(settings, "GROQ_MODEL", "llama-3.3-70b-versatile")
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=150
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as exc:
        logger.warning("Failed to generate AI outreach message: %s", exc)
        return f"Hi {lead_name}, I came across your profile and was impressed with your experience. I'd love to connect and learn more about your work."


async def _generate_ai_reply_message(user_id: str, lead: dict, conv: dict, outbound_actions: list) -> str:
    from app.config.groq_config import get_groq_client
    from app.config.settings import settings
    
    lead_name = lead.get("name", "there")
    company = lead.get("company", "your company")
    focus = lead.get("focus", "")
    
    history_str = ""
    if outbound_actions:
        history_str += "Outbound Messages Sent:\n"
        for act in sorted(outbound_actions, key=lambda x: x.get("created_at") or ""):
            history_str += f"- {act.get('message')}\n"
            
    last_inbound = conv.get("last_message_preview", "") if conv else ""
    if last_inbound:
        history_str += f"Inbound Reply Received:\n\"{last_inbound}\"\n"
        
    system_prompt = (
        "You are an expert sales assistant drafting a response to a lead's LinkedIn reply. "
        "Analyze the message history and the lead's response. Write a professional, context-aware reply. "
        "Do NOT use placeholders like [Your Name] or emojis. End with a polite sign-off."
    )
    user_prompt = f"Lead: {lead_name} at {company} ({focus})\n\nHistory:\n{history_str}\nDraft response:"
    
    try:
        client = get_groq_client(user_id)
        model = getattr(settings, "GROQ_MODEL", "llama-3.3-70b-versatile")
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=250
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as exc:
        logger.warning("Failed to generate AI reply message: %s", exc)
        return f"Hi {lead_name}, thank you for your response. I'd love to learn more about your current initiatives."


async def execute_tool(name: str, args: dict, user_id: str, uploaded_files: list = None, background_tasks = None, chat_session_id: str = None) -> str:
    """Execute the corresponding tool function and return output as a string."""
    db = await get_database()
    _uploaded_files = uploaded_files or []

    try:


        if name == "list_campaigns":
            campaigns = await get_campaigns(user_id=user_id, limit=50)
            return json.dumps(campaigns, default=str)

        elif name == "create_campaign":
            # Check for attached files in the message
            attachments = []
            if _uploaded_files:
                attachments = _uploaded_files

            # The LLM often serialises sequence_steps as a JSON string instead of
            # a list.  Parse it here so Pydantic's validator receives a proper list.
            raw_steps = args.get("sequence_steps")
            if isinstance(raw_steps, str):
                try:
                    raw_steps = json.loads(raw_steps)
                except (json.JSONDecodeError, ValueError):
                    raw_steps = None  # fall back to no steps

            campaign_data = CampaignCreate(
                name=args["name"],
                description=args.get("description", ""),
                subject_template=args.get("subject_template", "Outreach"),
                body_template=args.get("body_template", "Hi {{first_name}}"),
                gmail_account_id=args.get("gmail_account_id", ""),
                sequence_steps=raw_steps,
                settings=CampaignSettings()
            )
            campaign = await create_campaign(user_id=user_id, data=campaign_data)

            # Store attachments in campaign if any
            if attachments:
                db_campaigns = db.campaigns
                await db_campaigns.update_one(
                    {"id": campaign["id"]},
                    {"$set": {"attachments": attachments}}
                )
                campaign["attachments"] = attachments

            return json.dumps({"status": "success", "campaign": campaign}, default=str)

        elif name == "start_campaign":
            campaign_id = args.get("campaign_id", "")
            # If no campaign_id, find the most recent draft/paused campaign
            if not campaign_id:
                campaign = await db.campaigns.find_one(
                    {"user_id": user_id, "status": {"$in": ["draft", "paused"]}},
                    sort=[("created_at", -1)]
                )
                if campaign:
                    campaign_id = campaign["id"]
                else:
                    return json.dumps({"error": "No draft or paused campaigns found to start"})
            
            # Resolve campaign name to ID if needed
            if campaign_id and not _is_uuid(campaign_id):
                campaign = await db.campaigns.find_one({
                    "name": {"$regex": f"^{re.escape(campaign_id)}$", "$options": "i"},
                    "user_id": user_id
                })
                if campaign:
                    campaign_id = campaign["id"]
                else:
                    return json.dumps({"error": f"Campaign '{campaign_id}' not found"})
            
            # Verify campaign exists and belongs to user
            verify = await db.campaigns.find_one({"id": campaign_id, "user_id": user_id})
            if not verify:
                return json.dumps({"error": f"Campaign '{campaign_id}' not found"})
            
            # Check if already active
            if verify.get("status") == "active":
                return json.dumps({"status": "already_active", "message": f"Campaign '{verify.get('name')}' is already active", "campaign": verify}, default=str)
            
            campaign = await start_campaign(campaign_id=campaign_id, user_id=user_id)
            return json.dumps({"status": "success", "message": "Campaign started", "campaign": campaign}, default=str)

        elif name == "pause_campaign":
            campaign_id = args.get("campaign_id", "")
            # If no campaign_id, find the most recent active campaign
            if not campaign_id:
                campaign = await db.campaigns.find_one(
                    {"user_id": user_id, "status": "active"},
                    sort=[("created_at", -1)]
                )
                if campaign:
                    campaign_id = campaign["id"]
                else:
                    return json.dumps({"error": "No active campaigns found to pause"})
            
            # Resolve campaign name to ID if needed
            if campaign_id and not _is_uuid(campaign_id):
                campaign = await db.campaigns.find_one({
                    "name": {"$regex": f"^{re.escape(campaign_id)}$", "$options": "i"},
                    "user_id": user_id
                })
                if campaign:
                    campaign_id = campaign["id"]
                else:
                    return json.dumps({"error": f"Campaign '{campaign_id}' not found"})
            
            # Verify campaign exists and belongs to user
            verify = await db.campaigns.find_one({"id": campaign_id, "user_id": user_id})
            if not verify:
                return json.dumps({"error": f"Campaign '{campaign_id}' not found"})
            
            # Check if already paused
            if verify.get("status") == "paused":
                return json.dumps({"status": "already_paused", "message": f"Campaign '{verify.get('name')}' is already paused", "campaign": verify}, default=str)
            
            campaign = await pause_campaign(campaign_id=campaign_id, user_id=user_id)
            return json.dumps({"status": "success", "message": "Campaign paused", "campaign": campaign}, default=str)

        elif name == "delete_campaign":
            campaign_id = await _resolve_campaign_id(args.get("campaign_id"), user_id, db)
            await db.campaigns.update_one(
                {"id": campaign_id, "user_id": user_id},
                {"$set": {"status": "deleted", "updated_at": datetime.now(timezone.utc)}}
            )
            return json.dumps({"status": "success", "message": f"Campaign {campaign_id} deleted"})

        elif name == "duplicate_campaign":
            campaign_id = await _resolve_campaign_id(args.get("campaign_id"), user_id, db)
            original = await db.campaigns.find_one({"id": campaign_id, "user_id": user_id}, {"_id": 0})
            if not original:
                return json.dumps({"error": "Campaign not found"})
            from app.utils.id_generator import generate_id
            now = datetime.now(timezone.utc)
            new_campaign = {
                "id": generate_id(),
                "user_id": user_id,
                "name": f"{original['name']} (Copy)",
                "description": original.get("description", ""),
                "gmail_account_id": original.get("gmail_account_id", ""),
                "subject_template": original.get("subject_template", ""),
                "body_template": original.get("body_template", ""),
                "followup_enabled": original.get("followup_enabled", True),
                "followup_stages": original.get("followup_stages", 3),
                "followup_delay_days": original.get("followup_delay_days", 3),
                "daily_send_limit": original.get("daily_send_limit", 50),
                "status": "draft",
                "total_leads": 0,
                "emails_sent": 0,
                "created_at": now,
                "updated_at": now,
            }
            await db.campaigns.insert_one(new_campaign)
            new_campaign.pop("_id", None)
            return json.dumps({"status": "success", "campaign": new_campaign}, default=str)

        elif name == "search_campaigns_by_email":
            email = args["email"].lower()
            campaigns = await db.campaigns.find(
                {"user_id": user_id, "email_list": email},
                {"_id": 0}
            ).to_list(50)
            return json.dumps(campaigns, default=str)

        elif name == "get_campaign_analytics":
            campaign_id = await _resolve_campaign_id(args.get("campaign_id"), user_id, db)
            stats = await get_campaign_stats(campaign_id=campaign_id)
            return json.dumps(stats, default=str)

        # ── Lead Tools ──────────────────────────────────────────────────
        elif name == "list_leads":
            campaign_id = await _resolve_campaign_id(args.get("campaign_id"), user_id, db)
            leads = await get_leads(campaign_id=campaign_id, user_id=user_id, limit=50)
            return json.dumps(leads, default=str)

        elif name == "add_lead":
            email_value = args.get("email", "").strip()
            if not _validate_email(email_value):
                return json.dumps({"error": f"Invalid email: '{email_value}'. Use format: name@example.com"})

            campaign_id = args.get("campaign_id", "")

            # Resolve campaign name to ID if needed
            if campaign_id and not _is_uuid(campaign_id):
                # It's a campaign name, find the ID
                campaign = await db.campaigns.find_one({
                    "name": {"$regex": f"^{re.escape(campaign_id)}$", "$options": "i"},
                    "user_id": user_id
                })
                if campaign:
                    campaign_id = campaign["id"]
                else:
                    # Auto-create the campaign if the LLM provided a name but it wasn't found
                    default = CampaignCreate(name=campaign_id if campaign_id != "/" else "New AI Campaign", settings=CampaignSettings())
                    result = await create_campaign(user_id=user_id, data=default)
                    campaign_id = result["id"]

            if not campaign_id:
                campaign = await db.campaigns.find_one({"user_id": user_id, "status": {"$ne": "deleted"}})
                if campaign:
                    campaign_id = campaign["id"]
                else:
                    default = CampaignCreate(name="Default Campaign", settings=CampaignSettings())
                    result = await create_campaign(user_id=user_id, data=default)
                    campaign_id = result["id"]

            lead_data = LeadCreate(
                name=args["name"],
                email=email_value,
                company=args.get("company", ""),
                role=args.get("role", ""),
                website=args.get("website", ""),
                campaign_id=campaign_id
            )
            lead = await create_lead(user_id=user_id, data=lead_data)
            return json.dumps({"status": "success", "lead": lead, "campaign_id": campaign_id}, default=str)

        elif name == "bulk_add_leads":
            leads_data = args.get("leads", [])
            campaign_id = await _resolve_campaign_id(args.get("campaign_id", ""), user_id, db)
            if not campaign_id:
                campaign = await db.campaigns.find_one({"user_id": user_id})
                if campaign:
                    campaign_id = campaign["id"]

            results = []
            for lead in leads_data:
                email = lead.get("email", "").strip()
                if not _validate_email(email):
                    results.append({"email": email, "status": "invalid_email"})
                    continue
                try:
                    lead_create = LeadCreate(
                        name=lead.get("name", ""),
                        email=email,
                        company=lead.get("company", ""),
                        role=lead.get("role", ""),
                        campaign_id=campaign_id
                    )
                    await create_lead(user_id=user_id, data=lead_create)
                    results.append({"email": email, "status": "success"})
                except Exception as e:
                    results.append({"email": email, "status": "error", "error": str(e)})

            return json.dumps({"status": "success", "results": results, "campaign_id": campaign_id}, default=str)

        elif name == "move_leads":
            source_campaign_id = await _resolve_campaign_id(args["source_campaign_id"], user_id, db)
            target_campaign_id = await _resolve_campaign_id(args["target_campaign_id"], user_id, db)
            result = await db.leads.update_many(
                {"campaign_id": source_campaign_id, "user_id": user_id},
                {"$set": {"campaign_id": target_campaign_id, "updated_at": datetime.now(timezone.utc)}}
            )
            return json.dumps({"status": "success", "moved": result.modified_count})

        elif name == "delete_lead":
            lead_id = args["lead_id"]
            await db.leads.delete_one({"id": lead_id, "user_id": user_id})
            return json.dumps({"status": "success", "message": f"Lead {lead_id} deleted"})

        elif name == "search_leads":
            query = args.get("query", "")
            leads = await db.leads.find(
                {"user_id": user_id, "$or": [
                    {"name": {"$regex": query, "$options": "i"}},
                    {"email": {"$regex": query, "$options": "i"}},
                    {"company": {"$regex": query, "$options": "i"}},
                ]},
                {"_id": 0}
            ).to_list(50)
            return json.dumps(leads, default=str)

        # ── Gmail Account Tools ─────────────────────────────────────────
        elif name == "list_gmail_accounts":
            accounts = await db.gmail_accounts.find(
                {"user_id": user_id, "is_active": True},
                {"_id": 0, "access_token": 0, "refresh_token": 0}
            ).to_list(50)
            return json.dumps(accounts, default=str)

        elif name == "list_tracker_users":
            cursor = db.users.find(
                {},
                {"_id": 0, "id": 1, "name": 1, "display_name": 1, "email": 1, "role": 1}
            ).sort("display_name", 1)
            users = await cursor.to_list(length=100)
            return json.dumps(users, default=str)

        # ── Email Tools ─────────────────────────────────────────────────
        elif name == "list_emails":
            campaign_id = await _resolve_campaign_id(args.get("campaign_id"), user_id, db)
            query = {"user_id": user_id}
            if campaign_id:
                query["campaign_id"] = campaign_id
            emails = await db.emails.find(query, {"_id": 0}).sort("created_at", -1).to_list(50)
            return json.dumps(emails, default=str)

        elif name == "count_unread_emails":
            count = await db.emails.count_documents({"user_id": user_id, "status": "sent"})
            return json.dumps({"unread_count": count})

        elif name == "search_emails":
            query_text = args.get("query", "")
            emails = await db.emails.find(
                {"user_id": user_id, "$or": [
                    {"subject": {"$regex": query_text, "$options": "i"}},
                    {"to": {"$regex": query_text, "$options": "i"}},
                ]},
                {"_id": 0}
            ).to_list(50)
            return json.dumps(emails, default=str)

        # ── Reply/Tracking Tools ────────────────────────────────────────
        elif name == "list_replies":
            campaign_id = args.get("campaign_id")
            query = {}
            if campaign_id:
                query["campaign_id"] = campaign_id
            replies = await db.replies.find(query, {"_id": 0}).sort("received_at", -1).to_list(50)
            return json.dumps(replies, default=str)

        elif name == "get_reply_details":
            reply = await db.replies.find_one({"id": args["reply_id"]}, {"_id": 0})
            if not reply:
                return json.dumps({"error": "Reply not found"})
            return json.dumps(reply, default=str)

        # ── LinkedIn Tools ──────────────────────────────────────────────
        elif name == "linkedin_connection_request":
            import asyncio
            from app.utils.id_generator import generate_id
            linkedin_url = args["linkedin_url"]
            note = args.get("custom_note", "")
            try:
                if note:
                    action_id = generate_id()
                    action_doc = {
                        "id": action_id,
                        "user_id": user_id,
                        "linkedin_url": linkedin_url,
                        "action_type": "connection_request",
                        "status": "pending_approval",
                        "message": note,
                        "created_at": datetime.now(timezone.utc),
                    }
                    await db.linkedin_actions.insert_one(action_doc)
                    
                    # Also insert into pending_approvals
                    lead = await db.leads.find_one({"linkedin": linkedin_url, "user_id": user_id})
                    lead_id = lead["id"] if lead else ""
                    approval_doc = {
                        "action_id": action_id,
                        "user_id": user_id,
                        "action_type": "linkedin_connections",
                        "description": f"Send connection request to {linkedin_url}",
                        "count": 1,
                        "items": [linkedin_url],
                        "payload": {
                            "lead_ids": [lead_id] if lead_id else [],
                            "note": note,
                            "linkedin_url": linkedin_url
                        },
                        "status": "pending",
                        "chat_session_id": chat_session_id,
                        "created_at": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc),
                    }
                    await db.pending_approvals.insert_one(approval_doc)
                    
                    res = {
                        "status": "success",
                        "action_id": action_id,
                        "draft_message": note,
                        "status_text": "pending_approval"
                    }
                else:
                    action_id = generate_id()
                    async def run_workflow_bg():
                        try:
                            from orchestrator.engine import get_orchestrator
                            orchestrator = await get_orchestrator()
                            await orchestrator.execute_workflow(
                                "LinkedIn Connection Workflow",
                                inputs={
                                    "action_id": action_id,
                                    "linkedin_url": linkedin_url,
                                    "user_id": user_id,
                                    "lead_id": args.get("lead_id", ""),
                                    "timestamp": datetime.now(timezone.utc).isoformat(),
                                },
                                context={"user_id": user_id},
                            )
                            logger.info("LinkedIn Connection Workflow finished in background for %s", linkedin_url)
                        except Exception as e:
                            logger.exception("Background LinkedIn Connection Workflow failed: %s", e)

                    if background_tasks:
                        background_tasks.add_task(run_workflow_bg)
                    else:
                        import asyncio
                        asyncio.create_task(run_workflow_bg())
                    res = {
                        "status": "processing",
                        "action_id": action_id,
                        "message": "I have started researching the profile and drafting the connection request in the background. It will appear in your pending queue shortly.",
                        "status_text": "processing"
                    }
            except Exception as e:
                logger.exception("Chatbot connection request failed: %s", e)
                res = {"error": str(e)}
            return json.dumps(res, default=str)

        elif name == "linkedin_send_message":
            from app.utils.id_generator import generate_id
            linkedin_url = args["linkedin_url"]
            msg = args["message"]
            msg = await _resolve_message_templates(msg, user_id)
            try:
                action_id = generate_id()
                action_doc = {
                    "id": action_id,
                    "user_id": user_id,
                    "linkedin_url": linkedin_url,
                    "action_type": "message",
                    "status": "pending_approval",
                    "message": msg,
                    "created_at": datetime.now(timezone.utc),
                }
                await db.linkedin_actions.insert_one(action_doc)
                
                # Also insert into pending_approvals
                lead = await db.leads.find_one({"linkedin": linkedin_url, "user_id": user_id})
                lead_id = lead["id"] if lead else ""
                approval_doc = {
                    "action_id": action_id,
                    "user_id": user_id,
                    "action_type": "linkedin_messages",
                    "description": f"Send message to {linkedin_url}",
                    "count": 1,
                    "items": [linkedin_url],
                    "payload": {
                        "action_id": action_id,
                        "lead_ids": [lead_id] if lead_id else [],
                        "message": msg,
                        "linkedin_url": linkedin_url
                    },
                    "status": "pending",
                    "chat_session_id": chat_session_id,
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                }
                await db.pending_approvals.insert_one(approval_doc)
                
                res = {
                    "status": "success",
                    "action_id": action_id,
                    "draft_message": msg,
                    "status_text": "pending_approval",
                    "message": f"LinkedIn message drafted for {linkedin_url} and queued for approval."
                }
            except Exception as e:
                logger.exception("Chatbot message request failed: %s", e)
                res = {"error": str(e)}
            return json.dumps(res, default=str)

        elif name == "linkedin_send_message_by_name":
            from app.utils.id_generator import generate_id
            person_name = args["person_name"]
            msg = args["message"]
            msg = await _resolve_message_templates(msg, user_id)
            try:
                action_id = generate_id()
                action_doc = {
                    "id": action_id,
                    "user_id": user_id,
                    "linkedin_url": person_name,
                    "action_type": "message",
                    "status": "pending_approval",
                    "message": msg,
                    "created_at": datetime.now(timezone.utc),
                }
                await db.linkedin_actions.insert_one(action_doc)
                
                # Also insert into pending_approvals
                approval_doc = {
                    "action_id": action_id,
                    "user_id": user_id,
                    "action_type": "linkedin_messages",
                    "description": f"Send message to {person_name}",
                    "count": 1,
                    "items": [person_name],
                    "payload": {
                        "action_id": action_id,
                        "person_name": person_name,
                        "message": msg
                    },
                    "status": "pending",
                    "chat_session_id": chat_session_id,
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                }
                await db.pending_approvals.insert_one(approval_doc)
                
                res = {
                    "status": "success",
                    "action_id": action_id,
                    "draft_message": msg,
                    "status_text": "pending_approval",
                    "message": f"LinkedIn message to {person_name} drafted and queued for approval."
                }
            except Exception as e:
                logger.exception("Chatbot message by name failed: %s", e)
                res = {"error": str(e)}
            return json.dumps(res, default=str)

        elif name == "linkedin_scrape_profile":
            from app.services.linkedin_outreach_service import scrape_profile
            linkedin_url = args["linkedin_url"]
            res = await scrape_profile(linkedin_url, user_id)
            return json.dumps(res, default=str)

        elif name == "linkedin_check_inbox":
            from app.services.linkedin_outreach_service import get_pending_invitations
            res = await get_pending_invitations(user_id)
            return json.dumps(res, default=str)

        elif name == "linkedin_session_status":
            from app.services.linkedin_outreach_service import get_session_status
            res = await get_session_status(user_id)
            return json.dumps(res, default=str)

        elif name == "linkedin_manage_queue":
            action = args["action"]
            action_id = args.get("action_id")
            db = await get_database()
            if action == "list":
                actions = await db.linkedin_actions.find({"user_id": user_id, "status": "pending_approval"}).to_list(100)
                return json.dumps(actions, default=str)
            elif action == "approve":
                if not action_id:
                    return json.dumps({"error": "action_id is required to approve"})
                action_doc = await db.linkedin_actions.find_one({"id": action_id, "user_id": user_id})
                if not action_doc:
                    return json.dumps({"error": "Action not found"})
                if action_doc.get("status") not in ("pending_approval", "failed", "rejected"):
                    return json.dumps({"error": f"Action is already {action_doc.get('status')}"})
                action_type = action_doc.get("action_type")
                linkedin_url = action_doc.get("linkedin_url", "")
                message = action_doc.get("message", "")
                try:
                    if action_type == "connection_request":
                        from app.services.linkedin_outreach_service import send_connection_request
                        result = await send_connection_request(linkedin_url, message, user_id)
                    elif action_type in ("first_message", "message", "followup"):
                        target = linkedin_url or ""
                        if "linkedin.com" in target or target.startswith("http"):
                            from app.services.linkedin_outreach_service import send_message
                            result = await send_message(target, message, user_id)
                        else:
                            from app.services.linkedin_outreach_service import send_message_by_name
                            result = await send_message_by_name(target, message, user_id)
                    elif action_type in ("follow", "follow_profile"):
                        from app.services.linkedin_outreach_service import follow_profile
                        result = await follow_profile(linkedin_url, user_id)
                    else:
                        result = {"success": False, "error": f"Unknown action type: {action_type}"}
                    new_status = "executed" if result.get("success") else "failed"
                    await db.linkedin_actions.update_one(
                        {"id": action_id},
                        {"$set": {
                            "status": new_status,
                            "execution_result": result,
                            "executed_at": datetime.now(timezone.utc),
                            "updated_at": datetime.now(timezone.utc),
                        }}
                    )
                    if result.get("success") and action_type in ("connection_request", "first_message", "message", "followup"):
                        from app.services.linkedin_scheduler_service import increment_daily_count
                        await increment_daily_count(user_id, "connection" if action_type == "connection_request" else "message")
                    return json.dumps({"status": "success", "result": result, "action_status": new_status}, default=str)
                except Exception as exc:
                    return json.dumps({"status": "error", "error": str(exc)}, default=str)
            elif action == "reject":
                if not action_id:
                    return json.dumps({"error": "action_id is required to reject"})
                result = await db.linkedin_actions.update_one(
                    {"id": action_id, "user_id": user_id, "status": {"$in": ["pending_approval", "failed"]}},
                    {"$set": {"status": "rejected", "updated_at": datetime.now(timezone.utc)}}
                )
                if result.modified_count == 0:
                    return json.dumps({"error": "Action not found or not pending"})
                return json.dumps({"status": "success", "action_id": action_id, "action_status": "rejected"})
            else:
                return json.dumps({"error": f"Unknown queue action: {action}"})

        elif name == "linkedin_follow_profile":
            from app.utils.id_generator import generate_id
            linkedin_url = args["linkedin_url"]
            try:
                action_id = generate_id()
                action_doc = {
                    "id": action_id,
                    "user_id": user_id,
                    "linkedin_url": linkedin_url,
                    "action_type": "follow_profile",
                    "status": "pending_approval",
                    "message": "Follow profile/company",
                    "created_at": datetime.now(timezone.utc),
                }
                await db.linkedin_actions.insert_one(action_doc)
                
                # Also insert into pending_approvals
                approval_doc = {
                    "action_id": action_id,
                    "user_id": user_id,
                    "action_type": "linkedin_follow",
                    "description": f"Follow LinkedIn profile {linkedin_url}",
                    "count": 1,
                    "items": [linkedin_url],
                    "payload": {
                        "action_id": action_id,
                        "linkedin_url": linkedin_url
                    },
                    "status": "pending",
                    "chat_session_id": chat_session_id,
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                }
                await db.pending_approvals.insert_one(approval_doc)
                
                res = {
                    "status": "success",
                    "action_id": action_id,
                    "status_text": "pending_approval",
                    "message": f"LinkedIn follow action drafted for {linkedin_url} and queued for approval."
                }
            except Exception as e:
                logger.exception("Chatbot follow request failed: %s", e)
                res = {"error": str(e)}
            return json.dumps(res, default=str)

        elif name == "linkedin_query_memory":
            query = args["query"]
            try:
                from app.services.memory_service import AgentMemoryService
                context = await AgentMemoryService.retrieve_semantic_context(query)
                res = {
                    "status": "success",
                    "query": query,
                    "context": context
                }
            except Exception as e:
                logger.exception("Chatbot semantic memory query failed: %s", e)
                res = {"error": str(e)}
            return json.dumps(res, default=str)

        # ── Update Tools ────────────────────────────────────────────────
        elif name == "update_campaign":
            campaign_id = await _resolve_campaign_id(args.get("campaign_id"), user_id, db)
            update_fields = {}
            if "name" in args and args["name"]:
                update_fields["name"] = args["name"]
            if "description" in args and args["description"] is not None:
                update_fields["description"] = args["description"]
            if "subject_template" in args and args["subject_template"] is not None:
                update_fields["subject_template"] = args["subject_template"]
            if "body_template" in args and args["body_template"] is not None:
                update_fields["body_template"] = args["body_template"]
            if "daily_send_limit" in args and args["daily_send_limit"] is not None:
                update_fields["daily_send_limit"] = args["daily_send_limit"]
            if "followup_enabled" in args and args["followup_enabled"] is not None:
                update_fields["followup_enabled"] = args["followup_enabled"]
            if "followup_stages" in args and args["followup_stages"] is not None:
                update_fields["followup_stages"] = args["followup_stages"]
            if "sequence_steps" in args and args["sequence_steps"] is not None:
                update_fields["sequence_steps"] = args["sequence_steps"]

            if not update_fields:
                return json.dumps({"error": "No fields to update"})

            update_fields["updated_at"] = datetime.now(timezone.utc)
            result = await db.campaigns.update_one(
                {"id": campaign_id, "user_id": user_id},
                {"$set": update_fields}
            )
            if result.matched_count == 0:
                return json.dumps({"error": "Campaign not found"})
            updated = await db.campaigns.find_one({"id": campaign_id}, {"_id": 0})
            return json.dumps({"status": "success", "campaign": updated}, default=str)

        elif name == "update_lead":
            lead_id = args["lead_id"]
            update_fields = {}
            if "name" in args and args["name"]:
                update_fields["name"] = args["name"]
            if "email" in args and args["email"]:
                if not _validate_email(args["email"]):
                    return json.dumps({"error": f"Invalid email: {args['email']}"})
                update_fields["email"] = args["email"].lower().strip()
            if "company" in args and args["company"] is not None:
                update_fields["company"] = args["company"]
            if "role" in args and args["role"] is not None:
                update_fields["role"] = args["role"]
            if "website" in args and args["website"] is not None:
                update_fields["website"] = args["website"]
            if "status" in args and args["status"] is not None:
                update_fields["status"] = args["status"]
            if "score" in args and args["score"] is not None:
                update_fields["score"] = args["score"]

            if not update_fields:
                return json.dumps({"error": "No fields to update"})

            update_fields["updated_at"] = datetime.now(timezone.utc)
            result = await db.leads.update_one(
                {"id": lead_id, "user_id": user_id},
                {"$set": update_fields}
            )
            if result.matched_count == 0:
                return json.dumps({"error": "Lead not found"})
            updated = await db.leads.find_one({"id": lead_id}, {"_id": 0})
            return json.dumps({"status": "success", "lead": updated}, default=str)

        elif name == "update_lead_list":
            list_id = args["list_id"]
            update_fields = {}
            if "name" in args and args["name"]:
                update_fields["name"] = args["name"]
            if "description" in args and args["description"] is not None:
                update_fields["description"] = args["description"]

            if not update_fields:
                return json.dumps({"error": "No fields to update"})

            update_fields["updated_at"] = datetime.now(timezone.utc)
            result = await db.lead_lists.update_one(
                {"id": list_id, "user_id": user_id},
                {"$set": update_fields}
            )
            if result.matched_count == 0:
                return json.dumps({"error": "Lead list not found"})
            updated = await db.lead_lists.find_one({"id": list_id}, {"_id": 0})
            return json.dumps({"status": "success", "list": updated}, default=str)

        # ── Lead List Tools ─────────────────────────────────────────────
        elif name == "create_lead_list":
            from app.utils.id_generator import generate_id
            now = datetime.now(timezone.utc)
            list_doc = {
                "id": generate_id(),
                "user_id": user_id,
                "name": args["name"],
                "description": args.get("description", ""),
                "created_at": now,
                "updated_at": now,
            }
            await db.lead_lists.insert_one(list_doc)
            list_doc.pop("_id", None)
            return json.dumps({"status": "success", "list": list_doc}, default=str)

        elif name == "list_lead_lists":
            lists = await db.lead_lists.find({"user_id": user_id}, {"_id": 0}).to_list(50)
            for lst in lists:
                count = await db.leads.count_documents({"list_id": lst["id"]})
                lst["total_leads"] = count
            return json.dumps(lists, default=str)

        # ── Block List Tools ────────────────────────────────────────────
        elif name == "add_to_block_list":
            from app.utils.id_generator import generate_id
            value = args["value"].lower().strip()
            existing = await db.block_list.find_one({"user_id": user_id, "value": value})
            if existing:
                return json.dumps({"status": "already_exists", "value": value})
            entry = {
                "id": generate_id(),
                "user_id": user_id,
                "value": value,
                "reason": args.get("reason", ""),
                "created_at": datetime.now(timezone.utc),
            }
            await db.block_list.insert_one(entry)
            entry.pop("_id", None)
            return json.dumps({"status": "success", "entry": entry}, default=str)

        elif name == "list_block_list":
            entries = await db.block_list.find({"user_id": user_id}, {"_id": 0}).to_list(500)
            return json.dumps(entries, default=str)

        elif name == "import_leads_from_file":
            from app.services.linkedin_csv_import_service import import_leads_from_csv, extract_linkedin_urls_from_text

            file_url = args.get("file_url", "")
            campaign_id = await _resolve_campaign_id(args.get("campaign_id", ""), user_id, db)

            if not file_url:
                return json.dumps({"error": "file_url is required"})

            try:
                file_content = None
                filename = file_url.split("/")[-1]

                # ── Fast path: local /api/files/<file_id>/download URL ──────────
                # Avoid HTTP self-request (deadlock on single-threaded uvicorn).
                # Extract file_id from the URL and read directly from disk via DB.
                import re as _re
                _local_match = _re.search(r"/api/files/([^/]+)/download", file_url)
                if _local_match:
                    _file_id = _local_match.group(1)
                    _file_doc = await db.uploaded_files.find_one({"id": _file_id})
                    if _file_doc and _file_doc.get("file_path"):
                        import os as _os
                        _path = _file_doc["file_path"]
                        if _os.path.exists(_path):
                            with open(_path, "rb") as _f:
                                file_content = _f.read()
                            filename = _file_doc.get("original_filename", filename)
                        else:
                            return json.dumps({"error": f"Uploaded file not found on disk: {_path}"})
                    else:
                        return json.dumps({"error": f"File record not found for id: {_file_id}"})

                # ── Fallback: external URL (e.g. Google Drive, S3) ──────────────
                if file_content is None:
                    import httpx
                    async with httpx.AsyncClient(follow_redirects=True) as client:
                        response = await client.get(file_url, timeout=30.0)
                        if response.status_code != 200:
                            return json.dumps({"error": f"Failed to fetch file: {response.status_code}"})
                        file_content = response.content

                result = await import_leads_from_csv(
                    csv_content=file_content,
                    user_id=user_id,
                    campaign_id=campaign_id if campaign_id else None,
                    create_leads=True,
                )

                return json.dumps({
                    "status": "success",
                    "filename": filename,
                    "total_rows": result["total_rows"],
                    "valid_leads": result["valid_leads"],
                    "leads_created": result.get("leads_created", 0),
                    "leads": result["leads"][:10] if result.get("leads") else [],
                }, default=str)
            except Exception as e:
                logger.exception("Error importing leads from file")
                return json.dumps({"error": str(e)})

        elif name == "show_accepted_connections":
            limit = args.get("limit", 50)
            # Find leads who are connected but first message is not sent
            leads = await db.leads.find({
                "user_id": user_id,
                "linkedin_stage": "connected",
                "linkedin_first_message_sent": False
            }).sort("updated_at", -1).limit(limit).to_list(length=limit)

            if not leads:
                return json.dumps({
                    "response": "There are no new accepted connections awaiting outreach.",
                    "count": 0
                })

            # Pick the most recent one to queue for approval
            lead = leads[0]
            lead_name = lead.get("name", "Unknown")
            company = lead.get("company", "")
            focus = lead.get("focus", "")
            linkedin_url = lead.get("linkedin") or lead.get("linkedin_url", "")
            connected_at = lead.get("linkedin_connected_at")
            connected_at_str = connected_at.strftime("%Y-%m-%d %H:%M:%S") if connected_at else "Recently"

            # Generate first outreach message using LLM
            message = await _generate_ai_outreach_message(user_id, lead)

            # Insert pending action
            from app.utils.id_generator import generate_id
            action_id = generate_id()
            action_doc = {
                "id": action_id,
                "user_id": user_id,
                "lead_id": lead["id"],
                "linkedin_url": linkedin_url,
                "action_type": "message",
                "status": "pending_approval",
                "message": message,
                "created_at": datetime.now(timezone.utc),
            }
            await db.linkedin_actions.insert_one(action_doc)

            approval_doc = {
                "action_id": action_id,
                "user_id": user_id,
                "action_type": "linkedin_messages",
                "description": f"Suggested Message:\n\n{message}",
                "count": 1,
                "items": [linkedin_url],
                "payload": {
                    "action_id": action_id,
                    "lead_ids": [lead["id"]],
                    "message": message,
                    "linkedin_url": linkedin_url
                },
                "status": "pending",
                "chat_session_id": chat_session_id,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }
            await db.pending_approvals.insert_one(approval_doc)

            response_markdown = (
                f"### Accepted Connection Details\n"
                f"- **Lead**: {lead_name}\n"
                f"- **Company**: {company}\n"
                f"- **Focus area**: {focus}\n"
                f"- **LinkedIn profile**: {linkedin_url}\n"
                f"- **Acceptance date**: {connected_at_str}\n\n"
                f"I have generated a suggested first outreach message and queued it for your approval below."
            )

            return json.dumps({
                "response": response_markdown,
                "pending_approval": {
                    "action_id": action_id,
                    "action_type": "linkedin_messages",
                    "description": f"Suggested Message:\n\n{message}",
                    "count": 1,
                    "items": [linkedin_url],
                    "status": "pending"
                }
            }, default=str)

        elif name == "generate_reply":
            target_url = args.get("linkedin_url", "").strip()
            lead = None
            if target_url:
                lead = await db.leads.find_one({
                    "user_id": user_id,
                    "$or": [{"linkedin": target_url}, {"linkedin_url": target_url}]
                })
            else:
                # Find most recent lead who replied
                lead = await db.leads.find_one(
                    {"user_id": user_id, "linkedin_reply_received": True},
                    sort=[("updated_at", -1)]
                )

            if not lead:
                return json.dumps({
                    "response": "I couldn't find any recent LinkedIn replies to generate a response for.",
                })

            linkedin_url = lead.get("linkedin") or lead.get("linkedin_url", "")
            lead_name = lead.get("name", "Unknown")

            # Load message history
            conv = await db.linkedin_conversations.find_one({"user_id": user_id, "contact_linkedin_url": linkedin_url})
            outbound_actions = await db.linkedin_actions.find({
                "user_id": user_id,
                "linkedin_url": linkedin_url,
                "status": "executed"
            }).to_list(length=20)

            # Generate reply message using LLM
            message = await _generate_ai_reply_message(user_id, lead, conv, outbound_actions)

            # Insert pending action
            from app.utils.id_generator import generate_id
            action_id = generate_id()
            action_doc = {
                "id": action_id,
                "user_id": user_id,
                "lead_id": lead["id"],
                "linkedin_url": linkedin_url,
                "action_type": "message",
                "status": "pending_approval",
                "message": message,
                "created_at": datetime.now(timezone.utc),
            }
            await db.linkedin_actions.insert_one(action_doc)

            approval_doc = {
                "action_id": action_id,
                "user_id": user_id,
                "action_type": "linkedin_messages",
                "description": f"Suggested Reply:\n\n{message}",
                "count": 1,
                "items": [linkedin_url],
                "payload": {
                    "action_id": action_id,
                    "lead_ids": [lead["id"]],
                    "message": message,
                    "linkedin_url": linkedin_url
                },
                "status": "pending",
                "chat_session_id": chat_session_id,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }
            await db.pending_approvals.insert_one(approval_doc)

            response_markdown = (
                f"### Suggested Reply for {lead_name}\n"
                f"- **Company**: {lead.get('company', '')}\n"
                f"- **LinkedIn profile**: {linkedin_url}\n\n"
                f"I have generated a context-aware reply message below for your approval."
            )

            return json.dumps({
                "response": response_markdown,
                "pending_approval": {
                    "action_id": action_id,
                    "action_type": "linkedin_messages",
                    "description": f"Suggested Reply:\n\n{message}",
                    "count": 1,
                    "items": [linkedin_url],
                    "status": "pending"
                }
            }, default=str)

        elif name == "list_linkedin_leads":
            from app.services.linkedin_csv_import_service import get_linkedin_leads_for_outreach
            
            limit = args.get("limit", 100)
            result = await get_linkedin_leads_for_outreach(
                user_id=user_id,
                limit=min(limit, 500),
            )
            return json.dumps({"leads": result, "count": len(result)}, default=str)

        elif name == "bulk_linkedin_action":
            from app.utils.id_generator import generate_id
            lead_ids = args.get("lead_ids", [])
            action_type = args.get("action_type", "connection_request")
            message = args.get("message", "")
            note = args.get("note", "")
            
            if not lead_ids:
                return json.dumps({"error": "lead_ids is required"})
            
            if action_type == "send_message" and not message:
                return json.dumps({"error": "message is required for send_message action"})
            
            # Fetch lead names for preview
            leads_cursor = db.leads.find({"id": {"$in": lead_ids}, "user_id": user_id})
            leads = await leads_cursor.to_list(length=100)
            lead_names = [l.get("name") or l.get("email") for l in leads]
            
            action_id = generate_id()
            approval_doc = {
                "action_id": action_id,
                "user_id": user_id,
                "action_type": "linkedin_connections" if action_type == "connection_request" else "linkedin_messages",
                "description": f"Bulk {action_type.replace('_', ' ')} to {len(lead_ids)} leads",
                "count": len(lead_ids),
                "items": lead_names,
                "payload": {
                    "lead_ids": lead_ids,
                    "action_type": action_type,
                    "message": message,
                    "note": note,
                    "is_bulk": True
                },
                "status": "pending",
                "chat_session_id": chat_session_id,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }
            await db.pending_approvals.insert_one(approval_doc)
            
            res = {
                "status": "success",
                "action_id": action_id,
                "status_text": "pending_approval",
                "message": f"Bulk LinkedIn {action_type} for {len(lead_ids)} leads created and queued for approval."
            }
            return json.dumps(res, default=str)

        else:
            return json.dumps({"error": f"Tool '{name}' not found."})

    except Exception as e:
        logger.exception(f"Error executing tool {name}")
        return json.dumps({"error": str(e)})


# ── Tools metadata for Groq API ────────────────────────────────────────────

CHATBOT_TOOLS = [
    # ── Campaign Tools ──────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "list_campaigns",
            "description": "List all campaigns owned by the user. Use this to show current campaigns.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_campaign",
            "description": "Create a new outreach campaign. ALWAYS call this when user asks to create a campaign.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Campaign name. Extract from user message."},
                    "description": {"type": "string", "description": "Optional campaign description."},
                    "subject_template": {"type": "string", "description": "Email subject with {{first_name}} placeholders."},
                    "body_template": {"type": "string", "description": "Email body HTML with {{first_name}} placeholders."},
                    "sequence_steps": {
                        "type": "array",
                        "description": "Optional list of multi-step sequence steps. Each step has fields: step_number, channel ('email', 'linkedin', 'task'), delay_days, subject_template (for email), body_template (for email/linkedin), notes (for task).",
                        "items": {
                            "type": "object",
                            "properties": {
                                "step_number": {"type": "integer"},
                                "channel": {"type": "string", "enum": ["email", "linkedin", "task"]},
                                "delay_days": {"type": "integer"},
                                "subject_template": {"type": "string"},
                                "body_template": {"type": "string"},
                                "notes": {"type": "string"}
                            },
                            "required": ["step_number", "channel", "delay_days"]
                        }
                    }
                },
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "start_campaign",
            "description": "Start or resume a campaign. If no campaign specified, starts the most recent draft/paused campaign.",
            "parameters": {
                "type": "object",
                "properties": {
                    "campaign_id": {"type": "string", "description": "Optional campaign ID or name. If not provided, auto-selects the most recent draft/paused campaign."}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "pause_campaign",
            "description": "Pause an active campaign. If no campaign specified, pauses the most recent active campaign.",
            "parameters": {
                "type": "object",
                "properties": {
                    "campaign_id": {"type": "string", "description": "Optional campaign ID or name. If not provided, auto-selects the most recent active campaign."}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_campaign",
            "description": "Delete a campaign permanently.",
            "parameters": {
                "type": "object",
                "properties": {
                    "campaign_id": {"type": "string", "description": "Campaign ID to delete."}
                },
                "required": ["campaign_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "duplicate_campaign",
            "description": "Create a copy of an existing campaign with all settings.",
            "parameters": {
                "type": "object",
                "properties": {
                    "campaign_id": {"type": "string", "description": "Campaign ID to duplicate."}
                },
                "required": ["campaign_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_campaigns_by_email",
            "description": "Find campaigns that use a specific email address.",
            "parameters": {
                "type": "object",
                "properties": {
                    "email": {"type": "string", "description": "Email address to search for."}
                },
                "required": ["email"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_campaign_analytics",
            "description": "Get real-time analytics for a campaign: emails sent, open rate, click rate, reply rate.",
            "parameters": {
                "type": "object",
                "properties": {
                    "campaign_id": {"type": "string", "description": "Campaign ID."}
                },
                "required": ["campaign_id"]
            }
        }
    },
    # ── Lead Tools ──────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "list_leads",
            "description": "List leads. Optionally filter by campaign.",
            "parameters": {
                "type": "object",
                "properties": {
                    "campaign_id": {"type": "string", "description": "Optional campaign ID filter."}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_lead",
            "description": "Add a single lead with name and email. Email MUST be real format (name@example.com).",
            "parameters": {
                "type": "object",
                "properties": {
                    "campaign_id": {"type": "string", "description": "Campaign ID. Auto-selected if not provided."},
                    "name": {"type": "string", "description": "Full name of the lead."},
                    "email": {"type": "string", "description": "Real email address like john@example.com."},
                    "company": {"type": "string", "description": "Company name."},
                    "role": {"type": "string", "description": "Job title or role."},
                    "website": {"type": "string", "description": "Company website."},
                },
                "required": ["name", "email"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "bulk_add_leads",
            "description": "Add multiple leads at once. Provide list of leads with name and email.",
            "parameters": {
                "type": "object",
                "properties": {
                    "campaign_id": {"type": "string", "description": "Campaign ID. Auto-selected if not provided."},
                    "leads": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "email": {"type": "string"},
                                "company": {"type": "string"},
                                "role": {"type": "string"},
                            },
                            "required": ["name", "email"]
                        },
                        "description": "Array of leads to add."
                    }
                },
                "required": ["leads"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "move_leads",
            "description": "Move all leads from one campaign to another.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source_campaign_id": {"type": "string", "description": "Source campaign ID."},
                    "target_campaign_id": {"type": "string", "description": "Target campaign ID."}
                },
                "required": ["source_campaign_id", "target_campaign_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_lead",
            "description": "Delete a single lead.",
            "parameters": {
                "type": "object",
                "properties": {
                    "lead_id": {"type": "string", "description": "Lead ID to delete."}
                },
                "required": ["lead_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_leads",
            "description": "Search leads by name, email, or company.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query."}
                },
                "required": ["query"]
            }
        }
    },
    # ── Gmail Account Tools ─────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "list_gmail_accounts",
            "description": "List all connected Gmail accounts for sending emails.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_tracker_users",
            "description": "List all registered team members / users in the outreach tracker (e.g. John Doe, Supriya Gali) who can be assigned to leads.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    # ── Email Tools ─────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "list_emails",
            "description": "List sent emails. Optionally filter by campaign.",
            "parameters": {
                "type": "object",
                "properties": {
                    "campaign_id": {"type": "string", "description": "Optional campaign ID filter."}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "count_unread_emails",
            "description": "Count unread or pending emails.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_emails",
            "description": "Search emails by subject or recipient.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query."}
                },
                "required": ["query"]
            }
        }
    },
    # ── Reply Tools ─────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "list_replies",
            "description": "List received replies from leads.",
            "parameters": {
                "type": "object",
                "properties": {
                    "campaign_id": {"type": "string", "description": "Optional campaign ID filter."}
                }
            }
        }
    },
    # ── Update Tools ────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "update_campaign",
            "description": "Update a campaign's settings: name, description, subject, body, daily limit, follow-up settings.",
            "parameters": {
                "type": "object",
                "properties": {
                    "campaign_id": {"type": "string", "description": "Campaign ID to update."},
                    "name": {"type": "string", "description": "New campaign name."},
                    "description": {"type": "string", "description": "New description."},
                    "subject_template": {"type": "string", "description": "New email subject template."},
                    "body_template": {"type": "string", "description": "New email body template."},
                    "daily_send_limit": {"type": "integer", "description": "Max emails per day."},
                    "followup_enabled": {"type": "boolean", "description": "Enable follow-up emails."},
                    "followup_stages": {"type": "integer", "description": "Number of follow-up stages."},
                    "followup_delay_days": {"type": "integer", "description": "Days between follow-ups."},
                    "sequence_steps": {
                        "type": "array",
                        "description": "Optional list of multi-step sequence steps. Each step has fields: step_number, channel ('email', 'linkedin', 'task'), delay_days, subject_template (for email), body_template (for email/linkedin), notes (for task).",
                        "items": {
                            "type": "object",
                            "properties": {
                                "step_number": {"type": "integer"},
                                "channel": {"type": "string", "enum": ["email", "linkedin", "task"]},
                                "delay_days": {"type": "integer"},
                                "subject_template": {"type": "string"},
                                "body_template": {"type": "string"},
                                "notes": {"type": "string"}
                            },
                            "required": ["step_number", "channel", "delay_days"]
                        }
                    }
                },
                "required": ["campaign_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_lead",
            "description": "Update a lead's information: name, email, company, role, status, score.",
            "parameters": {
                "type": "object",
                "properties": {
                    "lead_id": {"type": "string", "description": "Lead ID to update."},
                    "name": {"type": "string", "description": "New name."},
                    "email": {"type": "string", "description": "New email address."},
                    "company": {"type": "string", "description": "New company name."},
                    "role": {"type": "string", "description": "New job title/role."},
                    "website": {"type": "string", "description": "New website URL."},
                    "status": {"type": "string", "description": "New status (new, contacted, engaged, qualified, converted, lost)."},
                    "score": {"type": "number", "description": "New lead score (0-100)."},
                },
                "required": ["lead_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_lead_list",
            "description": "Update a lead list's name or description.",
            "parameters": {
                "type": "object",
                "properties": {
                    "list_id": {"type": "string", "description": "Lead list ID to update."},
                    "name": {"type": "string", "description": "New list name."},
                    "description": {"type": "string", "description": "New description."},
                },
                "required": ["list_id"]
            }
        }
    },
    # ── Lead List Tools ─────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "create_lead_list",
            "description": "Create a new lead list for organizing contacts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "List name."},
                    "description": {"type": "string", "description": "Optional description."}
                },
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_lead_lists",
            "description": "List all lead lists with lead counts.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    # ── Block List Tools ────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "add_to_block_list",
            "description": "Block an email or domain from receiving emails.",
            "parameters": {
                "type": "object",
                "properties": {
                    "value": {"type": "string", "description": "Email or domain to block."},
                    "reason": {"type": "string", "description": "Optional reason."}
                },
                "required": ["value"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_block_list",
            "description": "List all blocked emails and domains.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "linkedin_connection_request",
            "description": "Send a LinkedIn connection request with an optional note to a profile URL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "linkedin_url": {"type": "string", "description": "The target LinkedIn profile URL."},
                    "custom_note": {"type": "string", "description": "Optional connection note message."}
                },
                "required": ["linkedin_url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "linkedin_send_message",
            "description": "Send a direct LinkedIn message to a connection using their profile URL. Uses Playwright browser automation to actually send the message.",
            "parameters": {
                "type": "object",
                "properties": {
                    "linkedin_url": {"type": "string", "description": "The target LinkedIn profile URL."},
                    "message": {"type": "string", "description": "The message body to send."}
                },
                "required": ["linkedin_url", "message"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "linkedin_send_message_by_name",
            "description": "Send a direct LinkedIn message to a connection by searching for them by name. Use this when the user wants to message someone by name (e.g. 'send message to John Doe') instead of providing a LinkedIn URL. Uses Playwright browser automation to search connections and send the message.",
            "parameters": {
                "type": "object",
                "properties": {
                    "person_name": {"type": "string", "description": "Full name of the LinkedIn connection to message."},
                    "message": {"type": "string", "description": "The message body to send."}
                },
                "required": ["person_name", "message"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "linkedin_scrape_profile",
            "description": "Scrape detailed profile information from a LinkedIn URL (name, headline, experience, about etc.) to personalize outreach.",
            "parameters": {
                "type": "object",
                "properties": {
                    "linkedin_url": {"type": "string", "description": "The target LinkedIn profile URL to scrape."}
                },
                "required": ["linkedin_url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "linkedin_check_inbox",
            "description": "Scan the LinkedIn inbox for new incoming messages and inspect recent connections or pending invitations.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "linkedin_session_status",
            "description": "Get the current authentication status of the user's LinkedIn account (connected, disconnected, expired).",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "linkedin_manage_queue",
            "description": "List all pending approval LinkedIn actions, or approve/reject/dismiss a specific action by ID from the queue.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["list", "approve", "reject"], "description": "The queue operation: list pending, approve, or reject an action."},
                    "action_id": {"type": "string", "description": "The action ID, required when action is approve or reject."}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "linkedin_follow_profile",
            "description": "Follow a target LinkedIn profile or company page using Playwright browser automation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "linkedin_url": {"type": "string", "description": "The target LinkedIn profile or company URL to follow."}
                },
                "required": ["linkedin_url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "linkedin_query_memory",
            "description": "Query the RAG semantic memory store (Qdrant) to retrieve context from emails, research summaries, and leads.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query or concept to look up in the memory database."}
                },
                "required": ["query"]
            }
        }
    },
    # ── File Import Tools ─────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "import_leads_from_file",
            "description": "Import LinkedIn leads from an uploaded CSV file. Extracts name, email, company, role, and LinkedIn URL from CSV rows.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_url": {"type": "string", "description": "URL of the uploaded file to import leads from (e.g., /api/files/{file_id}/download)."},
                    "campaign_id": {"type": "string", "description": "Optional campaign ID to associate leads with."}
                },
                "required": ["file_url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_linkedin_leads",
            "description": "List all LinkedIn leads ready for outreach (leads with LinkedIn URLs).",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Maximum number of leads to return (default 100, max 500)."}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "bulk_linkedin_action",
            "description": "Create bulk LinkedIn connection requests or send bulk messages to multiple leads.",
            "parameters": {
                "type": "object",
                "properties": {
                    "lead_ids": {"type": "array", "items": {"type": "string"}, "description": "List of lead IDs to create actions for."},
                    "action_type": {"type": "string", "enum": ["connection_request", "send_message"], "description": "Type of action to create."},
                    "message": {"type": "string", "description": "Message to send (required for send_message action)."},
                    "note": {"type": "string", "description": "Note for connection request (optional)."}
                },
                "required": ["lead_ids", "action_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "show_accepted_connections",
            "description": "Show list of leads who accepted connection requests and generate suggested outreach messages for each.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Maximum number of connections to return (default 50)."}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_reply",
            "description": "Read conversation history for a lead and generate an AI suggested reply message for user approval.",
            "parameters": {
                "type": "object",
                "properties": {
                    "linkedin_url": {"type": "string", "description": "LinkedIn URL of the contact to generate a reply for. If not provided, it will find the most recent unreplied conversation."}
                }
            }
        }
    },
]


# ── Rule-based fallback parser ─────────────────────────────────────────────

async def run_rule_based_fallback(user_id: str, message: str, background_tasks = None) -> Dict[str, Any] | None:
    """Parse message with regex and run automation. Used when Groq is unavailable."""
    if len(message) > 200000:
        return None

    db = await get_database()
    msg_lower = message.lower()

    async def resolve_campaign(identifier: str) -> str | None:
        campaign = await db.campaigns.find_one({"id": identifier, "user_id": user_id})
        if campaign:
            return identifier
        campaign = await db.campaigns.find_one({
            "name": re.compile(rf"^{re.escape(identifier)}$", re.IGNORECASE),
            "user_id": user_id
        })
        return campaign["id"] if campaign else None

    # 1. Create Campaign
    create_match = re.search(
        r"create\s+(?:a\s+)?(?:new\s+)?campaign\s+(?:named|called)?\s*['\"]?([\w\s\-\.]+?)['\"]?(?:\s+with|\s+subject|\.|\s*$)",
        message, re.IGNORECASE
    )
    if create_match:
        name = create_match.group(1).strip()
        subject_match = re.search(r"subject\s+(?:line\s+)?(?:of\s+)?['\"]?([^'\"]+?)['\"]?(?:\s+body|\.|\s*$)", message, re.IGNORECASE)
        body_match = re.search(r"body\s+(?:of\s+)?['\"]?([^'\"]+?)['\"]?(?:\.|\s*$)", message, re.IGNORECASE)
        args = {
            "name": name,
            "subject_template": subject_match.group(1) if subject_match else "Outreach",
            "body_template": body_match.group(1) if body_match else "Hi {{first_name}}"
        }
        res = await execute_tool("create_campaign", args, user_id)
        res_dict = json.loads(res)
        if "error" in res_dict:
            return {"response": f"Failed to create campaign '{name}': {res_dict['error']}", "actions_taken": []}
        return {
            "response": f"Created campaign **{name}** (ID: {res_dict['campaign']['id']}).",
            "actions_taken": [{"tool": "create_campaign", "arguments": args}]
        }

    # 2. Start Campaign
    start_match = re.search(r"start\s+(?:the\s+)?(?:campaign\s+)?['\"]?([\w\s\-\.]+?)['\"]?(?:\.|\s*$)", message, re.IGNORECASE)
    if start_match:
        identifier = start_match.group(1).strip()
        # If identifier is empty or just "campaign", find the most recent draft/paused
        if not identifier or identifier.lower() in ["campaign", "it", "the campaign"]:
            campaign = await db.campaigns.find_one(
                {"user_id": user_id, "status": {"$in": ["draft", "paused"]}},
                sort=[("created_at", -1)]
            )
            if campaign:
                campaign_id = campaign["id"]
                identifier = campaign["name"]
            else:
                return {"response": "No draft or paused campaigns found to start.", "actions_taken": []}
        else:
            campaign_id = await resolve_campaign(identifier)
            if not campaign_id:
                return {"response": f"Campaign '{identifier}' not found.", "actions_taken": []}
        res = await execute_tool("start_campaign", {"campaign_id": campaign_id}, user_id)
        return {"response": f"Campaign **{identifier}** started.", "actions_taken": [{"tool": "start_campaign", "arguments": {"campaign_id": campaign_id}}]}

    # 3. Pause Campaign
    pause_match = re.search(r"pause\s+(?:the\s+)?(?:campaign\s+)?['\"]?([\w\s\-\.]+?)['\"]?(?:\.|\s*$)", message, re.IGNORECASE)
    if pause_match:
        identifier = pause_match.group(1).strip()
        # If identifier is empty or just "campaign", find the most recent active
        if not identifier or identifier.lower() in ["campaign", "it", "the campaign"]:
            campaign = await db.campaigns.find_one(
                {"user_id": user_id, "status": "active"},
                sort=[("created_at", -1)]
            )
            if campaign:
                campaign_id = campaign["id"]
                identifier = campaign["name"]
            else:
                return {"response": "No active campaigns found to pause.", "actions_taken": []}
        else:
            campaign_id = await resolve_campaign(identifier)
            if not campaign_id:
                return {"response": f"Campaign '{identifier}' not found.", "actions_taken": []}
        res = await execute_tool("pause_campaign", {"campaign_id": campaign_id}, user_id)
        return {"response": f"Campaign **{identifier}** paused.", "actions_taken": [{"tool": "pause_campaign", "arguments": {"campaign_id": campaign_id}}]}

    # 4. List Campaigns
    if re.search(r"(?:list|show|get|display)\s+(?:all\s+)?(?:my\s+)?campaigns?", msg_lower):
        res = await execute_tool("list_campaigns", {}, user_id)
        campaigns = json.loads(res)
        if not campaigns:
            return {"response": "No campaigns found.", "actions_taken": [{"tool": "list_campaigns", "arguments": {}}]}
        formatted = "Your campaigns:\n"
        for c in campaigns:
            formatted += f"- **{c['name']}** | Status: `{c['status']}` | Leads: {c['total_leads']} | ID: `{c['id']}`\n"
        return {"response": formatted, "actions_taken": [{"tool": "list_campaigns", "arguments": {}}]}

    # 5. Add Lead
    add_match = re.search(
        r"add\s+(?:a\s+)?lead\s+['\"]?([^,'\"]+?)['\"]?,\s*['\"]?([^'\"]+\@[^'\"]+\.[^'\"]+?)['\"]?\s+to\s+(?:campaign\s+)?['\"]?([\w\s\-\.]+?)['\"]?(?:\.|\s*$)",
        message, re.IGNORECASE
    )
    if add_match:
        name = add_match.group(1).strip()
        email = add_match.group(2).strip()
        campaign_identifier = add_match.group(3).strip()
        campaign_id = await resolve_campaign(campaign_identifier)
        if not campaign_id:
            return {"response": f"Campaign '{campaign_identifier}' not found.", "actions_taken": []}
        args = {"campaign_id": campaign_id, "name": name, "email": email}
        res = await execute_tool("add_lead", args, user_id)
        return {"response": f"Added lead **{name}** ({email}).", "actions_taken": [{"tool": "add_lead", "arguments": args}]}

    # 6. List Leads
    list_leads_match = re.search(r"(?:list|show|get|display)\s+leads?(?:\s+(?:for|in)\s+(?:campaign\s+)?['\"]?([\w\s\-\.]+?)['\"]?)?", message, re.IGNORECASE)
    if list_leads_match:
        campaign_id = None
        campaign_name = "all campaigns"
        if list_leads_match.group(1):
            campaign_id = await resolve_campaign(list_leads_match.group(1).strip())
            campaign_name = list_leads_match.group(1).strip()
        res = await execute_tool("list_leads", {"campaign_id": campaign_id}, user_id)
        leads = json.loads(res)
        if not leads:
            return {"response": f"No leads found for {campaign_name}.", "actions_taken": []}
        formatted = f"Leads for {campaign_name}:\n"
        for l in leads:
            formatted += f"- **{l['name']}** | {l['email']} | {l.get('company', 'N/A')} | Status: `{l['status']}`\n"
        return {"response": formatted, "actions_taken": [{"tool": "list_leads", "arguments": {"campaign_id": campaign_id}}]}

    # 6b. List Tracker Users
    if re.search(r"(?:list|show|get|display)\s+(?:all\s+)?(?:tracker\s+|team\s+)?users?\b", msg_lower) or "usertab" in msg_lower:
        res = await execute_tool("list_tracker_users", {}, user_id)
        users = json.loads(res)
        if not users:
            return {"response": "No users found in the outreach tracker.", "actions_taken": []}
        formatted = "Registered users in the outreach tracker:\n"
        for idx, u in enumerate(users, 1):
            disp = u.get("display_name") or u.get("name", "Unknown")
            role_str = f" ({u.get('role')})" if u.get("role") else ""
            formatted += f"{idx}. **{disp}** - {u.get('email', 'No email')}{role_str}\n"
        return {"response": formatted, "actions_taken": [{"tool": "list_tracker_users", "arguments": {}}]}

    # 7. Analytics
    analytics_match = re.search(r"(?:analytics|stats|statistics|metrics)\s+(?:for|of)?\s*(?:campaign\s+)?['\"]?([\w\s\-\.]+?)['\"]?", message, re.IGNORECASE)
    if analytics_match:
        identifier = analytics_match.group(1).strip()
        campaign_id = await resolve_campaign(identifier)
        if not campaign_id:
            return {"response": f"Campaign '{identifier}' not found.", "actions_taken": []}
        res = await execute_tool("get_campaign_analytics", {"campaign_id": campaign_id}, user_id)
        stats = json.loads(res)
        formatted = (
            f"Analytics for **{identifier}**:\n"
            f"- Total Leads: {stats.get('total_leads', 0)}\n"
            f"- Emails Sent: {stats.get('emails_sent', 0)}\n"
            f"- Opens: {stats.get('total_opens', 0)} (Unique: {stats.get('unique_opens', 0)})\n"
            f"- Clicks: {stats.get('total_clicks', 0)}\n"
            f"- Replies: {stats.get('total_replies', 0)}\n"
            f"- Open Rate: {stats.get('open_rate', 0)}%\n"
            f"- Reply Rate: {stats.get('reply_rate', 0)}%"
        )
        return {"response": formatted, "actions_taken": [{"tool": "get_campaign_analytics", "arguments": {"campaign_id": campaign_id}}]}

    # 8. Update Campaign
    update_campaign_match = re.search(
        r"update\s+(?:campaign\s+)?['\"]?([\w\s\-\.]+?)['\"]?\s+(?:to\s+)?(?:named|called)?\s*(?:name\s+)?(?:to\s+)?['\"]?([\w\s\-\.]+?)['\"]?(?:\.|\s*$)",
        message, re.IGNORECASE
    )
    if update_campaign_match:
        identifier = update_campaign_match.group(1).strip()
        new_name = update_campaign_match.group(2).strip()
        campaign_id = await resolve_campaign(identifier)
        if not campaign_id:
            return {"response": f"Campaign '{identifier}' not found.", "actions_taken": []}
        args = {"campaign_id": campaign_id, "name": new_name}
        res = await execute_tool("update_campaign", args, user_id)
        return {"response": f"Campaign updated to **{new_name}**.", "actions_taken": [{"tool": "update_campaign", "arguments": args}]}

    # 9. Rename Campaign (simpler pattern)
    rename_match = re.search(
        r"rename\s+(?:campaign\s+)?['\"]?([\w\s\-\.]+?)['\"]?\s+(?:to|as)\s+['\"]?([\w\s\-\.]+?)['\"]?(?:\.|\s*$)",
        message, re.IGNORECASE
    )

    if rename_match:
        identifier = rename_match.group(1).strip()
        new_name = rename_match.group(2).strip()
        campaign_id = await resolve_campaign(identifier)
        if not campaign_id:
            return {"response": f"Campaign '{identifier}' not found.", "actions_taken": []}
        args = {"campaign_id": campaign_id, "name": new_name}
        res = await execute_tool("update_campaign", args, user_id)
        return {"response": f"Campaign renamed to **{new_name}**.", "actions_taken": [{"tool": "update_campaign", "arguments": args}]}

    # 10. LinkedIn Connection Request & Message
    linkedin_match = re.search(
        r"(?:send\s+(?:a\s+)?connection\s+request\s+to|connect\s+(?:with|to))\s+([^\s,]+)(?:\s+and\s+send\s+message\s+(.+))?",
        message, re.IGNORECASE
    )
    if linkedin_match:
        url = linkedin_match.group(1).strip()
        if not url.startswith("http"):
            url = "https://" + url
        custom_msg = linkedin_match.group(2).strip() if linkedin_match.group(2) else ""
        
        actions = []
        res1_str = await execute_tool("linkedin_connection_request", {"linkedin_url": url}, user_id, background_tasks=background_tasks)
        res1 = json.loads(res1_str)
        actions.append({"tool": "linkedin_connection_request", "arguments": {"linkedin_url": url}})
        
        if "error" in res1:
            return {"response": f"Failed to queue connection request: {res1['error']}", "actions_taken": actions}
            
        if res1.get("status") == "processing" or res1.get("status_text") == "processing":
            response_text = (
                f"I have started researching the profile for **{url}** and drafting a connection request in the background.\n"
                f"- **Status**: `processing`\n\n"
                f"It will appear in your queue shortly. Once it is ready, you can find it in the dashboard queue or approve it by typing `approve action <action_id>` (type `list queue` to find the ID)."
            )
        else:
            action_id = res1.get("action_id", "Unknown")
            draft_note = res1.get("draft_message", "")
            
            response_text = (
                f"Generated and queued a LinkedIn connection request draft for **{url}**.\n"
                f"- **Action ID**: `{action_id}`\n"
                f"- **Status**: `pending_approval`\n"
                f"- **Draft Note**: \"{draft_note}\"\n\n"
                f"You can approve this request from the dashboard queue or by telling me: `approve action {action_id}`."
            )
        
        if custom_msg:
            res2_str = await execute_tool("linkedin_send_message", {"linkedin_url": url, "message": custom_msg}, user_id)
            res2 = json.loads(res2_str)
            actions.append({"tool": "linkedin_send_message", "arguments": {"linkedin_url": url, "message": custom_msg}})
            if "error" in res2:
                response_text += f"\n\nFailed to queue direct message: {res2['error']}"
            else:
                msg_action_id = res2.get("action_id", "Unknown")
                response_text += (
                    f"\n\nAlso generated and queued a direct LinkedIn message draft:\n"
                    f"- **Action ID**: `{msg_action_id}`\n"
                    f"- **Status**: `pending_approval`\n"
                    f"- **Message**: \"{custom_msg}\"\n\n"
                    f"You can approve it by telling me: `approve action {msg_action_id}`."
                )
            
        return {"response": response_text, "actions_taken": actions}

    # 10b. LinkedIn Direct Message (Independent) — by URL or by Name
    # Try two patterns: one with "from my connection" delimiter, one without
    direct_msg_match = re.search(
        r"send\s+(?:a\s+)?(?:direct\s+)?message\s+to\s+(.+?)\s+from\s+my\s+connection\s+(?:saying|with\s+text|with\s+message)(?:\s*:\s*|\s+)['\"]?(.+?)['\"]?(?:\s+(?:on|in)\s+(?:the\s+)?linkedin)?(?:\.|\s*$)",
        message, re.IGNORECASE
    )
    if direct_msg_match:
        target = direct_msg_match.group(1).strip()
        msg_text = direct_msg_match.group(2).strip()
        
        actions = []
        
        # Determine if target is a URL or a person's name
        is_url = target.startswith("http") or "linkedin.com" in target.lower()
        
        if is_url:
            if not target.startswith("http"):
                target = "https://" + target
            res_str = await execute_tool("linkedin_send_message", {"linkedin_url": target, "message": msg_text}, user_id)
            res = json.loads(res_str)
            actions.append({"tool": "linkedin_send_message", "arguments": {"linkedin_url": target, "message": msg_text}})
            
            if res.get("status") == "success":
                action_id = res.get("action_id", "Unknown")
                response_text = (
                    f"Generated and queued a direct LinkedIn message draft for **{target}**.\n"
                    f"- **Action ID**: `{action_id}`\n"
                    f"- **Status**: `pending_approval`\n"
                    f"- **Message**: \"{msg_text}\"\n\n"
                    f"You can approve this request from the dashboard queue or by telling me: `approve action {action_id}`."
                )
            else:
                error = res.get("error", "Unknown error")
                response_text = f"❌ Failed to queue message: {error}"
        else:
            # It's a person's name — use send_message_by_name
            res_str = await execute_tool("linkedin_send_message_by_name", {"person_name": target, "message": msg_text}, user_id)
            res = json.loads(res_str)
            actions.append({"tool": "linkedin_send_message_by_name", "arguments": {"person_name": target, "message": msg_text}})
            
            if res.get("status") == "success":
                action_id = res.get("action_id", "Unknown")
                response_text = (
                    f"Generated and queued a direct LinkedIn message draft for **{target}**.\n"
                    f"- **Action ID**: `{action_id}`\n"
                    f"- **Status**: `pending_approval`\n"
                    f"- **Message**: \"{msg_text}\"\n\n"
                    f"You can approve this request from the dashboard queue or by telling me: `approve action {action_id}`."
                )
            else:
                error = res.get("error", "Unknown error")
                response_text = f"❌ Failed to queue message to {target}: {error}"
        
        return {"response": response_text, "actions_taken": actions}

    # 10c. LinkedIn Direct Message — normal pattern (no "from my connection")
    direct_msg_match2 = re.search(
        r"send\s+(?:a\s+)?(?:direct\s+)?message\s+to\s+(.+?)(?:\s+(?:saying|with\s+text|with\s+message)(?:\s*:\s*|\s+)['\"]?|\s*:\s*['\"]?)(.+?)['\"]?(?:\s+(?:on|in)\s+(?:the\s+)?linkedin)?(?:\.|\s*$)",
        message, re.IGNORECASE
    )
    if direct_msg_match2:
        target = direct_msg_match2.group(1).strip()
        msg_text = direct_msg_match2.group(2).strip()
        
        actions = []
        
        # Determine if target is a URL or a person's name
        is_url = target.startswith("http") or "linkedin.com" in target.lower()
        
        if is_url:
            if not target.startswith("http"):
                target = "https://" + target
            res_str = await execute_tool("linkedin_send_message", {"linkedin_url": target, "message": msg_text}, user_id)
            res = json.loads(res_str)
            actions.append({"tool": "linkedin_send_message", "arguments": {"linkedin_url": target, "message": msg_text}})
            
            if res.get("status") == "success":
                action_id = res.get("action_id", "Unknown")
                response_text = (
                    f"Generated and queued a direct LinkedIn message draft for **{target}**.\n"
                    f"- **Action ID**: `{action_id}`\n"
                    f"- **Status**: `pending_approval`\n"
                    f"- **Message**: \"{msg_text}\"\n\n"
                    f"You can approve this request from the dashboard queue or by telling me: `approve action {action_id}`."
                )
            else:
                error = res.get("error", "Unknown error")
                response_text = f"❌ Failed to queue message: {error}"
        else:
            # It's a person's name — use send_message_by_name
            res_str = await execute_tool("linkedin_send_message_by_name", {"person_name": target, "message": msg_text}, user_id)
            res = json.loads(res_str)
            actions.append({"tool": "linkedin_send_message_by_name", "arguments": {"person_name": target, "message": msg_text}})

            if res.get("status") == "success":
                action_id = res.get("action_id", "Unknown")
                response_text = (
                    f"Generated and queued a direct LinkedIn message draft for **{target}**.\n"
                    f"- **Action ID**: `{action_id}`\n"
                    f"- **Status**: `pending_approval`\n"
                    f"- **Message**: \"{msg_text}\"\n\n"
                    f"You can approve this request from the dashboard queue or by telling me: `approve action {action_id}`."
                )
            else:
                error = res.get("error", "Unknown error")
                response_text = f"❌ Failed to queue message to {target}: {error}"
        
        return {"response": response_text, "actions_taken": actions}

    # 11. LinkedIn Scrape Profile
    scrape_match = re.search(
        r"(?:scrape|extract|get details?)\b.*\b(linkedin\.com/in/[^\s]+)",
        message, re.IGNORECASE
    )
    if scrape_match:
        url = scrape_match.group(1).strip()
        if not url.startswith("http"):
            url = "https://" + url
        res = await execute_tool("linkedin_scrape_profile", {"linkedin_url": url}, user_id)
        res_dict = json.loads(res)
        if "error" in res_dict:
            return {"response": f"Failed to scrape profile: {res_dict['error']}", "actions_taken": []}
        summary = (
            f"Successfully scraped **{res_dict.get('name', 'Unknown')}**:\n"
            f"- Headline: {res_dict.get('headline', 'N/A')}\n"
            f"- Location: {res_dict.get('location', 'N/A')}\n"
            f"- About: {res_dict.get('about', 'N/A')[:150]}..."
        )
        return {"response": summary, "actions_taken": [{"tool": "linkedin_scrape_profile", "arguments": {"linkedin_url": url}}]}

    # 12. LinkedIn Check Inbox
    inbox_match = re.search(
        r"(?:check|read|get|unread)\b.*\b(?:inbox|messages|replies|conversations)\b",
        msg_lower
    )
    if inbox_match:
        res = await execute_tool("linkedin_check_inbox", {}, user_id)
        res_dict = json.loads(res)
        summary = "Checked LinkedIn inbox:\n"
        acc = res_dict.get("accepted_connections", [])
        pending = res_dict.get("pending_invitations", [])
        msgs = res_dict.get("new_messages", [])
        summary += f"- Accepted connections found: {len(acc)}\n"
        summary += f"- Pending invitations: {len(pending)}\n"
        summary += f"- Unread messages: {len(msgs)}\n"
        if msgs:
            summary += "\nUnread Messages preview:\n"
            for m in msgs[:3]:
                summary += f"- **{m.get('from_name')}**: {m.get('preview')} (Profile: {m.get('linkedin_url')})\n"
        return {"response": summary, "actions_taken": [{"tool": "linkedin_check_inbox", "arguments": {}}]}

    # 13. LinkedIn Session Status
    status_match = re.search(
        r"\b(?:check|is|status)\b.*\b(?:linkedin|connected|logged)\b",
        msg_lower
    )
    if status_match:
        res = await execute_tool("linkedin_session_status", {}, user_id)
        res_dict = json.loads(res)
        status = res_dict.get("status", "disconnected")
        last_val = res_dict.get("last_validated_at")
        val_str = f" (Last checked: {last_val})" if last_val else ""
        return {
            "response": f"LinkedIn Session Status: **{status.upper()}**{val_str}.",
            "actions_taken": [{"tool": "linkedin_session_status", "arguments": {}}]
        }

    # 14. LinkedIn Approve Action
    approve_match = re.search(
        r"approve\s+(?:action\s+)?([a-f0-9-]+)",
        msg_lower
    )
    if approve_match:
        action_id = approve_match.group(1).strip()
        res_str = await execute_tool("linkedin_manage_queue", {"action": "approve", "action_id": action_id}, user_id)
        res = json.loads(res_str)
        if "error" in res:
            return {"response": f"Failed to approve action `{action_id}`: {res['error']}", "actions_taken": []}
        return {
            "response": f"Action `{action_id}` has been approved and executed successfully.",
            "actions_taken": [{"tool": "linkedin_manage_queue", "arguments": {"action": "approve", "action_id": action_id}}]
        }

    # 15. LinkedIn Reject Action
    reject_match = re.search(
        r"reject\s+(?:action\s+)?([a-f0-9-]+)",
        msg_lower
    )
    if reject_match:
        action_id = reject_match.group(1).strip()
        res_str = await execute_tool("linkedin_manage_queue", {"action": "reject", "action_id": action_id}, user_id)
        res = json.loads(res_str)
        if "error" in res:
            return {"response": f"Failed to reject action `{action_id}`: {res['error']}", "actions_taken": []}
        return {
            "response": f"Action `{action_id}` has been rejected and removed from queue.",
            "actions_taken": [{"tool": "linkedin_manage_queue", "arguments": {"action": "reject", "action_id": action_id}}]
        }

    # 15b. LinkedIn Follow Profile
    follow_match = re.search(
        r"follow\s+(?:profile\s+|company\s+)?([^\s,]+)(?:\s+(?:on|in)\s+(?:the\s+)?linkedin)?(?:\.|\s*$)",
        message, re.IGNORECASE
    )
    if follow_match:
        url = follow_match.group(1).strip()
        if not url.startswith("http"):
            url = "https://" + url
        res_str = await execute_tool("linkedin_follow_profile", {"linkedin_url": url}, user_id)
        res = json.loads(res_str)
        if "error" in res:
            return {"response": f"Failed to follow profile: {res['error']}", "actions_taken": []}
        action_id = res.get("action_id", "Unknown")
        return {
            "response": (
                f"Generated and queued a LinkedIn follow action for **{url}**.\n"
                f"- **Action ID**: `{action_id}`\n"
                f"- **Status**: `pending_approval`\n\n"
                f"You can approve it by telling me: `approve action {action_id}`."
            ),
            "actions_taken": [{"tool": "linkedin_follow_profile", "arguments": {"linkedin_url": url}}]
        }

    # 15c. LinkedIn Query Memory
    query_memory_match = re.search(
        r"(?:query|search|lookup)\s+(?:semantic\s+)?(?:memory\s+|qdrant\s+|rag\s+)(?:store\s+|database\s+)?(?:for|about)?\s*['\"]?([^'\"]+?)['\"]?(?:\.|\s*$)",
        message, re.IGNORECASE
    )
    if query_memory_match:
        query_text = query_memory_match.group(1).strip()
        res_str = await execute_tool("linkedin_query_memory", {"query": query_text}, user_id)
        res = json.loads(res_str)
        if "error" in res:
            return {"response": f"Failed to query memory: {res['error']}", "actions_taken": []}
        
        context = res.get("context", {})
        emails = context.get("successful_emails", [])
        replies = context.get("past_replies", [])
        
        response_text = f"Semantic search results for: *\"{query_text}\"*\n\n"
        if emails:
            response_text += "**Successful Emails Context:**\n"
            for e in emails[:2]:
                response_text += f"- (Score: {e.get('score')}) {e.get('text')[:150]}...\n"
        if replies:
            response_text += "\n**Past Replies Context:**\n"
            for r in replies[:2]:
                response_text += f"- (Score: {r.get('score')}) {r.get('text')[:150]}...\n"
        if not emails and not replies:
            response_text += "No semantic context found in the memory store matching that query."
            
        return {
            "response": response_text,
            "actions_taken": [{"tool": "linkedin_query_memory", "arguments": {"query": query_text}}]
        }

    # 15d. Show Accepted Connections
    if re.search(r"\bshow\s+(?:new\s+)?accepted\s+(?:connections?|leads?)\b", msg_lower) or re.search(r"\baccepted\s+(?:connections?|leads?)\b", msg_lower):
        res_str = await execute_tool("show_accepted_connections", {}, user_id)
        res = json.loads(res_str)
        if "error" in res:
            return {"response": f"Failed to retrieve accepted connections: {res['error']}", "actions_taken": []}
        return {
            "response": res.get("response", ""),
            "actions_taken": [{"tool": "show_accepted_connections", "arguments": {}}],
            "pending_approval": res.get("pending_approval")
        }

    # 15e. Generate Reply
    gen_reply_match = re.search(
        r"(?:generate|suggest|draft)\s+(?:a\s+)?(?:reply|response)\s+(?:for|to)\s+([^\s,]+)",
        message, re.IGNORECASE
    )
    if gen_reply_match or re.search(r"\bgenerate\s+(?:a\s+)?(?:reply|response)\b", msg_lower) or re.search(r"\bdraft\s+(?:a\s+)?(?:reply|response)\b", msg_lower):
        target_url = gen_reply_match.group(1).strip() if gen_reply_match else ""
        if target_url and not target_url.startswith("http") and "linkedin.com" not in target_url:
            # If target_url is a name rather than a URL, let's search for a lead with that name
            lead = await db.leads.find_one({
                "user_id": user_id,
                "name": {"$regex": f"^{re.escape(target_url)}$", "$options": "i"}
            })
            if lead:
                target_url = lead.get("linkedin") or lead.get("linkedin_url", "")
        
        args = {}
        if target_url:
            args["linkedin_url"] = target_url
            
        res_str = await execute_tool("generate_reply", args, user_id)
        res = json.loads(res_str)
        if "error" in res:
            return {"response": f"Failed to generate reply: {res['error']}", "actions_taken": []}
        return {
            "response": res.get("response", ""),
            "actions_taken": [{"tool": "generate_reply", "arguments": args}],
            "pending_approval": res.get("pending_approval")
        }

    return None


# ── Main chat handler ──────────────────────────────────────────────────────

async def handle_chatbot_chat(
    user_id: str,
    message: str,
    conversation_history: List[Dict[str, str]] = None,
    uploaded_files: List[Dict[str, str]] = None,
    background_tasks = None,
    llm_provider: str = None,
    llm_model: str = None,
    chat_session_id: str = None,
) -> Dict[str, Any]:
    """
    Process chatbot message with tool calling. Falls back to rule-based parser if needed.
    
    Args:
        uploaded_files: List of file dicts with 'name', 'url', 'type' keys
    """
    # Store uploaded files for use in tool execution
    _current_uploaded_files = uploaded_files or []
    
    db = await get_database()
    user = await db.users.find_one({"id": user_id})
    user_name = user.get("name", "") if user else ""
    user_email = user.get("email", "") if user else ""

    config = await db.system_settings.find_one({"user_id": user_id, "type": "ai_config"})
    db_api_key = config.get("llm_api_key", "") if config else ""

    active_provider = (llm_provider or getattr(settings, "LLM_PROVIDER", "nvidia")).lower()
    if active_provider == "nvidia":
        active_model = llm_model or getattr(settings, "NVIDIA_NIM_MODEL", "moonshotai/kimi-k2.6")
        api_key = db_api_key or settings.NVIDIA_NIM_API_KEY
    elif active_provider == "xiaomi":
        active_model = llm_model or getattr(settings, "XIAOMI_MODEL", "mimo-v2.5")
        api_key = db_api_key or settings.XIAOMI_API_KEY
    else:
        active_model = llm_model or getattr(settings, "GROQ_MODEL", "llama-3.3-70b-versatile")
        api_key = db_api_key or settings.GROQ_API_KEY

    is_key_empty = not api_key or api_key.strip() in ("", '""', "''", "None")
    if is_key_empty:
        fallback_res = await run_rule_based_fallback(user_id, message, background_tasks=background_tasks)
        if fallback_res:
            return fallback_res
        return {
            "response": (
                f"Elly offline (API_KEY not set). Available commands:\n"
                "- **List campaigns**: 'list campaigns'\n"
                "- **Create campaign**: 'create campaign named X'\n"
                "- **Start campaign**: 'start campaign X'\n"
                "- **Pause campaign**: 'pause campaign X'\n"
                "- **Add lead**: 'add lead Name, email@example.com to campaign X'\n"
                "- **List leads**: 'list leads'\n"
                "- **List tracker users**: 'list tracker users'\n"
                "- **Analytics**: 'analytics for campaign X'"
            ),
            "actions_taken": []
        }


    history = conversation_history or []
    messages = [
        {
            "role": "system",
            "content": (
                "You are an Autonomous Campaign Management Agent named Elly with 29 tools. "
                "You MUST use tools to perform actions when requested. NEVER just describe what you would do. "
                "However, for general greetings (like 'Hi', 'Hello', 'Hi elly'), conversational questions, or questions about your capabilities, "
                "do NOT call any tools. Respond conversationally as Elly, introduce yourself, and ask how you can help.\n\n"
                f"You are executing actions on behalf of the user: {user_name} ({user_email}). "
                "When drafting campaign subject or body templates, use {{sender_name}} and {{sender_email}} to refer to the sender, "
                "or directly insert the user's name/email as the sender details. Do NOT use hardcoded placeholders like '[Your Name]' or '[Your Email]' in the templates. "
                "When drafting a direct message or connection request note to a person, always end the message with a polite sign-off followed by `{{sender_name}}` (e.g. `Best,\n{{sender_name}}`), unless they explicitly ask you not to include a signature.\n\n"
                "You can also create or update campaigns with multi-step sequences by passing a list of `sequence_steps` objects (each step has fields: step_number, channel ('email', 'linkedin', or 'task'), delay_days, subject_template (for email), body_template (for email/linkedin), notes (for task)).\n\n"
                "CRITICAL RULES - READ CAREFULLY:\n"
                "1. 'create campaign X' → Call create_campaign tool. This CREATES a NEW campaign.\n"
                "2. 'start the campaign' or 'start campaign X' → Call start_campaign tool. This STARTS an EXISTING campaign. Do NOT create a new one.\n"
                "3. 'pause the campaign' → Call pause_campaign tool. This PAUSES an EXISTING campaign.\n"
                "4. NEVER create a new campaign when user asks to START or PAUSE an existing one.\n"
                "5. 'list campaigns' → Call list_campaigns tool.\n"
                "6. 'add lead Name email@example.com' → Call add_lead tool. If there are multiple leads, ALWAYS use the bulk_add_leads tool to add them all at once.\n"
                "7. 'analytics for campaign X' → Call get_campaign_analytics tool.\n"
                "8. 'delete campaign X' → Call delete_campaign tool.\n"
                "9. 'update campaign X name Y' → Call update_campaign tool.\n"
                "10. 'rename campaign X to Y' → Call update_campaign tool with name=Y.\n"
                "11. 'list leads' → Call list_leads tool.\n"
                "12. 'search leads X' → Call search_leads tool.\n"
                "13. 'list emails' → Call list_emails tool.\n"
                "14. 'list gmail accounts' → Call list_gmail_accounts tool.\n"
                "15. 'duplicate campaign X' → Call duplicate_campaign tool.\n"
                "16. 'connect with <url>' or 'send connection request to <url>' → Call linkedin_connection_request tool. This will run the connection/research workflow asynchronously in the background (generating a personalized connection note and queueing it as pending_approval). The tool will return status: 'processing'. Explain to the user that you have started researching and drafting in the background, and they will be able to review/approve it in the queue once complete.\n"
                "17. 'send message to <url> saying <text>' → Call linkedin_send_message tool. This will draft the message and queue it in the database for approval with status 'pending_approval'. Explain to the user that you have drafted the message and queued it for their review/approval.\n"
                "25. 'send message to <person name> saying <text>' (where person name is NOT a URL) → Call linkedin_send_message_by_name tool. This will draft the message and queue it in the database for approval with status 'pending_approval'. Explain to the user that you have drafted the message and queued it for their review/approval. IMPORTANT: If the target is a person's name (not a LinkedIn URL), ALWAYS use linkedin_send_message_by_name, NOT linkedin_send_message.\n"
                "18. 'scrape profile <url>' → Call linkedin_scrape_profile tool.\n"
                "19. 'check inbox' or 'get messages' → Call linkedin_check_inbox tool.\n"
                "20. 'linkedin status' → Call linkedin_session_status tool.\n"
                "21. 'approve action <id>' or 'reject action <id>' → Call linkedin_manage_queue tool with appropriate action and action_id.\n"
                "22. 'import leads from file' or 'upload CSV' → Call import_leads_from_file tool with the file_url from uploaded_files. The user can attach a CSV file to import LinkedIn leads. Extract the file_url from the uploaded_files parameter and pass it to the tool.\n"
                "23. 'list linkedin leads' → Call list_linkedin_leads tool to show all leads with LinkedIn URLs.\n"
                "24. 'bulk connect <lead_ids>' or 'send bulk message' → Call bulk_linkedin_action tool to create bulk connection requests or messages for multiple leads.\n"
                "27. list tracker users or list team members or list users → Call list_tracker_users tool. Use this when the user asks to see registered team members/users instead of leads.\n"
                "28. For general conversation, greetings, politeness, or questions about your capabilities, do NOT call any tools. Answer conversationally in plain text as Elly.\n"
                "29. NEVER use emojis in any of your responses, conversations, or generated text.\n\n"
                "After tool executes, confirm what was done. If a tool returns a processing status, tell the user that the action has been kicked off in the background and will appear in their pending queue shortly.\n"
                "Use smart defaults: subject='Outreach', body='Hi {{first_name}}'.\n\n"
                "FILE UPLOAD SUPPORT:\n"
                "When user uploads a CSV file for lead import, the file info is in the uploaded_files parameter. Extract the 'url' field from each file object and use it with import_leads_from_file tool."
            )
        }
    ]

    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": message})

    actions_taken = []
    executed_tools = set()  # Track executed tool calls to prevent duplicates
    tool_already_called = False  # Track if we already called a tool this iteration

    # Force tool usage for action keywords
    action_keywords = ["create", "list", "add", "start", "pause", "delete", "show", "get", "analytics",
                       "search", "move", "duplicate", "block", "email", "lead", "campaign",
                       "scrape", "connect", "inbox", "status", "queue", "approve", "reject",
                       "send", "message"]
    force_tool = any(kw in message.lower() for kw in action_keywords)

    # Track which destructive tools have been called (prevent duplicates)
    destructive_tools = {"delete_campaign"}

    for _ in range(5):
        try:
            chat_completion = llm_chat_completion(
                messages=messages,
                model=active_model,
                provider=active_provider,
                tools=CHATBOT_TOOLS,
                tool_choice="required" if force_tool and not tool_already_called else "auto",
                temperature=0.3,
                user_id=user_id
            )
        except Exception as e:
            # If tool_choice="required" fails, retry with "auto"
            error_str = str(e).lower()
            if any(term in error_str for term in ["tool choice", "tool_choice", "tool use", "tool_use"]):
                try:
                    chat_completion = llm_chat_completion(
                        messages=messages,
                        model=active_model,
                        provider=active_provider,
                        tools=CHATBOT_TOOLS,
                        tool_choice="auto",
                        temperature=0.3,
                        user_id=user_id
                    )
                except Exception as e2:
                    logger.exception("Error calling LLM (retry)")
                    fallback_res = await run_rule_based_fallback(user_id, message, background_tasks=background_tasks)
                    if fallback_res:
                        return fallback_res
                    return {"response": f"AI model error: {e2}", "actions_taken": actions_taken}
            else:
                logger.exception("Error calling LLM")
                fallback_res = await run_rule_based_fallback(user_id, message, background_tasks=background_tasks)
                if fallback_res:
                    return fallback_res
                return {"response": f"AI model error: {e}", "actions_taken": actions_taken}

        response_message = chat_completion.choices[0].message

        if not response_message.tool_calls:
            assistant_content = response_message.content or ""
            if not actions_taken:
                fallback_res = await run_rule_based_fallback(user_id, message, background_tasks=background_tasks)
                if fallback_res and fallback_res.get("actions_taken"):
                    return fallback_res
            
            # Look for pending approvals in the tool outputs
            pending_approval = None
            for m in messages:
                if m.get("role") == "tool":
                    try:
                        out_data = json.loads(m["content"])
                        if isinstance(out_data, dict) and "action_id" in out_data:
                            action_id = out_data["action_id"]
                            app_doc = await db.pending_approvals.find_one({"action_id": action_id})
                            if app_doc:
                                app_doc.pop("_id", None)
                                pending_approval = app_doc
                                break
                    except Exception:
                        pass
                        
            return {
                "response": assistant_content,
                "actions_taken": actions_taken,
                "pending_approval": pending_approval
            }

        # Convert response_message to dict to avoid serialization issues
        msg_dict = {
            "role": "assistant",
            "content": response_message.content or ""
        }
        if response_message.tool_calls:
            msg_dict["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                } for tc in response_message.tool_calls
            ]
        messages.append(msg_dict)

        # Check if all tool calls are duplicates - if so, break
        new_tool_calls = []
        for tool_call in response_message.tool_calls:
            tool_key = f"{tool_call.function.name}:{tool_call.function.arguments}"
            if tool_key not in executed_tools:
                new_tool_calls.append(tool_call)
                executed_tools.add(tool_key)

        if not new_tool_calls:
            # All tools were duplicates, break to avoid infinite loop
            break

        for tool_call in new_tool_calls:
            tool_name = tool_call.function.name
            tool_args = json.loads(tool_call.function.arguments)
            actions_taken.append({"tool": tool_name, "arguments": tool_args})
            tool_output = await execute_tool(name=tool_name, args=tool_args, user_id=user_id, uploaded_files=_current_uploaded_files, background_tasks=background_tasks, chat_session_id=chat_session_id)
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": tool_name,
                "content": tool_output
            })
            tool_already_called = True  # Don't force tool on next iteration

        # If a destructive tool was executed, don't loop again
        if any(tc.function.name in destructive_tools for tc in new_tool_calls):
            break

    try:
        final_completion = llm_chat_completion(
            messages=messages,
            model=active_model,
            provider=active_provider,
            temperature=0.3,
            user_id=user_id
        )
        # Look for pending approvals in the tool outputs
        pending_approval = None
        for m in messages:
            if m.get("role") == "tool":
                try:
                    out_data = json.loads(m["content"])
                    if isinstance(out_data, dict) and "action_id" in out_data:
                        action_id = out_data["action_id"]
                        app_doc = await db.pending_approvals.find_one({"action_id": action_id})
                        if app_doc:
                            app_doc.pop("_id", None)
                            pending_approval = app_doc
                            break
                except Exception:
                    pass
        return {
            "response": final_completion.choices[0].message.content or "",
            "actions_taken": actions_taken,
            "pending_approval": pending_approval
        }
    except Exception as e:
        # If final response fails, return a summary of what was done
        pending_approval = None
        for m in messages:
            if m.get("role") == "tool":
                try:
                    out_data = json.loads(m["content"])
                    if isinstance(out_data, dict) and "action_id" in out_data:
                        action_id = out_data["action_id"]
                        app_doc = await db.pending_approvals.find_one({"action_id": action_id})
                        if app_doc:
                            app_doc.pop("_id", None)
                            pending_approval = app_doc
                            break
                except Exception:
                    pass
        if actions_taken:
            summary = "Actions completed:\n"
            for action in actions_taken:
                summary += f"- {action['tool']}: {json.dumps(action['arguments'])}\n"
            return {"response": summary, "actions_taken": actions_taken, "pending_approval": pending_approval}
        return {"response": f"Response generation failed: {e}", "actions_taken": actions_taken}
