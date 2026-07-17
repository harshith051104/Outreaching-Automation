"""
Campaign API routes.

Full CRUD for campaigns plus start/pause and stats endpoints.
"""

from fastapi import APIRouter, Depends, Query, status

from app.auth.dependencies import get_current_user
from app.schemas.campaign import CampaignCreate, CampaignUpdate, CampaignResponse
from app.services.campaign_service import (
    create_campaign,
    get_campaigns,
    get_campaign,
    update_campaign,
    start_campaign,
    pause_campaign,
    delete_campaign,
    get_campaign_stats,
)

router = APIRouter(prefix="/campaigns", tags=["Campaigns"])



@router.get("/check_formatting")
async def check_formatting():
    from app.config.mongodb_config import get_database
    db = await get_database()
    emails = await db.emails.find({"status": "sent"}).sort("sent_at", -1).limit(5).to_list(length=5)
    return [{"to": e["to"], "subject": e["subject"], "body_html": e["body_html"]} for e in emails]


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED, summary="Create a new campaign")
async def create(
    data: CampaignCreate,
    current_user: dict = Depends(get_current_user),
):
    """Create a new outreach campaign."""
    return await create_campaign(current_user["id"], data)


@router.get("", summary="List campaigns")
async def list_campaigns(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    """List all campaigns for the current user (newest first)."""
    return await get_campaigns(current_user["id"], skip=skip, limit=limit)


@router.get("/{campaign_id}", response_model=dict, summary="Get campaign")
async def get_campaign_by_id(
    campaign_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get a single campaign by ID."""
    return await get_campaign(campaign_id, current_user["id"])


@router.put("/{campaign_id}", response_model=dict, summary="Update campaign")
async def update(
    campaign_id: str,
    data: CampaignUpdate,
    current_user: dict = Depends(get_current_user),
):
    """Update mutable fields of a campaign."""
    return await update_campaign(campaign_id, current_user["id"], data)


@router.delete("/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete campaign")
async def delete(
    campaign_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Soft-delete a campaign (marks as deleted)."""
    await delete_campaign(campaign_id, current_user["id"])
    return None


@router.post("/{campaign_id}/start", response_model=dict, summary="Start campaign")
async def start(
    campaign_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Set campaign to active and queue for execution."""
    return await start_campaign(campaign_id, current_user["id"])


@router.post("/{campaign_id}/pause", response_model=dict, summary="Pause campaign")
async def pause(
    campaign_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Pause an active campaign (no new emails will be sent)."""
    return await pause_campaign(campaign_id, current_user["id"])


@router.get("/{campaign_id}/stats", response_model=dict, summary="Get campaign stats")
async def stats(
    campaign_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Return aggregated open/click/reply stats for a campaign."""
    await get_campaign(campaign_id, current_user["id"])
    return await get_campaign_stats(campaign_id)


@router.delete("/{campaign_id}/ai-cache/{lead_id}", summary="Clear AI placeholder cache for a lead")
async def clear_ai_cache(
    campaign_id: str,
    lead_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Clear cached AI-generated placeholder values so they regenerate on next send."""
    await get_campaign(campaign_id, current_user["id"])
    from app.tasks.campaign_tasks import _clear_cached_placeholders
    await _clear_cached_placeholders(campaign_id, lead_id)
    return {"status": "cleared", "campaign_id": campaign_id, "lead_id": lead_id}


@router.get("/debug/dump", summary="Debug DB Dump")
async def debug_dump():
    from app.config.mongodb_config import get_database
    from fastapi.responses import PlainTextResponse
    import json
    import os
    db = await get_database()
    campaigns = await db.campaigns.find({}, {"_id": 0}).to_list(length=100)
    leads_summary = {}
    for camp in campaigns:
        camp_id = camp.get("id")
        leads_count = await db.leads.count_documents({"campaign_id": camp_id})
        leads_summary[camp_id] = leads_count
    sample_leads = await db.leads.find({}, {"_id": 0}).limit(10).to_list(length=10)
    emails = await db.emails.find({}, {"_id": 0}).to_list(length=100)
    gmail_accounts = await db.gmail_accounts.find({}, {"_id": 0, "access_token": 0, "refresh_token": 0}).to_list(length=100)
    system_settings = await db.system_settings.find({}, {"_id": 0}).to_list(length=100)
    scheduled_tasks = await db.scheduled_tasks.find({}, {"_id": 0}).to_list(length=200)
    
    data = {
        "campaigns": campaigns,
        "leads_summary": leads_summary,
        "sample_leads": sample_leads,
        "emails": emails,
        "gmail_accounts": gmail_accounts,
        "system_settings": system_settings,
        "scheduled_tasks": scheduled_tasks
    }
    
    # Save to a file in the workspace
    filepath = "c:/Users/sriha/My work/Outreach/ai_outreach_v2_md_agents/scratch/db_dump.json"
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
        
    return PlainTextResponse(f"Saved database dump to {filepath}")


@router.get("/debug/kill_all", summary="Kill all Uvicorn, Celery, and Node processes")
async def kill_all_processes():
    import os
    import subprocess
    
    # 1. Kill node processes (frontend)
    try:
        subprocess.run(["taskkill", "/F", "/IM", "node.exe"], capture_output=True)
    except Exception:
        pass
        
    # 2. Find and kill Python processes running celery or uvicorn
    try:
        import psutil
        current_pid = os.getpid()
        to_kill = []
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmd = proc.info.get('cmdline') or []
                cmd_str = " ".join(cmd).lower()
                name = proc.info.get('name') or ""
                pid = proc.info.get('pid')
                if pid == current_pid:
                    continue
                
                # Check if it is a python/celery/uvicorn process related to our project
                is_related = False
                if "celery" in cmd_str or "uvicorn" in cmd_str or "celery_worker" in cmd_str:
                    is_related = True
                elif "python" in name.lower() or "python" in cmd_str:
                    # Check parent command line or cwd
                    try:
                        cwd = proc.cwd()
                        if "outreach" in cwd.lower():
                            is_related = True
                    except Exception:
                        pass
                    if not is_related and "outreach" in cmd_str:
                        is_related = True
                        
                if is_related:
                    to_kill.append(pid)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
                
        for pid in to_kill:
            try:
                subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
            except Exception:
                pass
    except Exception:
        # Fallback: kill celery workers via powershell
        try:
            subprocess.run(["powershell", "-Command", "Get-Process python | Where-Object {$_.CommandLine -match 'celery'} | Stop-Process -Force"], capture_output=True)
        except Exception:
            pass

    # 3. Finally, kill this uvicorn process itself after a brief delay
    import asyncio
    async def self_kill():
        await asyncio.sleep(1.0)
        os.kill(os.getpid(), 9)
        
    asyncio.create_task(self_kill())
    
    return {"status": "terminating", "message": "Triggered termination of all Celery, Uvicorn, and Node processes."}


@router.get("/debug/enable_llm", summary="Enable all LLMs globally and in memory")
async def enable_llm():
    from app.config.mongodb_config import get_database
    from app.config.groq_config import set_llm_section_disabled
    from datetime import datetime, timezone
    
    db = await get_database()
    
    # 1. Update memory toggles
    set_llm_section_disabled("campaigns", False)
    set_llm_section_disabled("reply_monitor", False)
    set_llm_section_disabled("linkedin", False)
    set_llm_section_disabled("chatbot", False)
    
    # 2. Update DB toggles
    for key in ["disable_llm", "disable_llm_campaigns", "disable_llm_reply_monitor", "disable_llm_linkedin"]:
        await db.system_settings.update_one(
            {"key": key},
            {"$set": {
                "value": False,
                "updated_at": datetime.now(timezone.utc)
            }},
            upsert=True
        )
        
    return {"status": "success", "message": "LLM calls have been enabled globally and across all sections."}


@router.get("/debug/check_leads", summary="Check leads task and email status")
async def debug_check_leads(campaign_id: str | None = None, task_id: str | None = None):
    from app.config.mongodb_config import get_database
    db = await get_database()
    
    if not task_id:
        # Find the most recently updated scheduled task
        recent_task = await db.scheduled_tasks.find_one({}, sort=[("updated_at", -1)])
        if recent_task:
            task_id = recent_task["id"]
            
    task = await db.scheduled_tasks.find_one({"id": task_id}) if task_id else None
    task_info = None
    if task:
        lead = await db.leads.find_one({"id": task.get("lead_id")})
        task_info = {
            "id": task.get("id"),
            "status": task.get("status"),
            "campaign_id": task.get("campaign_id"),
            "lead_id": task.get("lead_id"),
            "lead_name": lead.get("name") if lead else None,
            "lead_email": lead.get("email") if lead else None,
            "scheduled_at": str(task.get("scheduled_at")),
            "executed_at": str(task.get("executed_at")),
            "error": task.get("error"),
            "updated_at": str(task.get("updated_at"))
        }
        
    stuck_tasks = await db.scheduled_tasks.find({"status": "processing"}).to_list(length=100)
    stuck_info = []
    for st in stuck_tasks:
        lead = await db.leads.find_one({"id": st.get("lead_id")})
        stuck_info.append({
            "id": st["id"],
            "lead_name": lead.get("name") if lead else None,
            "scheduled_at": str(st.get("scheduled_at")),
            "updated_at": str(st.get("updated_at"))
        })
        
    pending_tasks = await db.scheduled_tasks.find({"status": "pending"}).to_list(length=100)
    pending_info = []
    for pt in pending_tasks:
        lead = await db.leads.find_one({"id": pt.get("lead_id")})
        pending_info.append({
            "id": pt["id"],
            "lead_name": lead.get("name") if lead else None,
            "scheduled_at": str(pt.get("scheduled_at")),
            "error": pt.get("error")
        })
        
    recent_emails = await db.emails.find({}).sort("sent_at", -1).to_list(length=20)
    email_list = []
    for e in recent_emails:
        email_list.append({
            "to": e["to"],
            "subject": e["subject"],
            "status": e["status"],
            "sent_at": str(e.get("sent_at")),
            "body_snippet": e.get("body_html", "")[:200]
        })
        
    return {
        "target_task": task_info,
        "stuck_processing_count": len(stuck_tasks),
        "stuck_processing_tasks": stuck_info,
        "pending_count": len(pending_tasks),
        "pending_tasks": pending_info,
        "recent_emails": email_list
    }


@router.get("/debug/processes", summary="List running Python and Celery processes")
async def debug_processes():
    import psutil
    import os
    from datetime import datetime
    
    import app
    current_pid = os.getpid()
    python_processes = []
    
    for proc in psutil.process_iter(['pid', 'name', 'create_time', 'cmdline']):
        try:
            cmd = proc.info.get('cmdline') or []
            cmd_str = " ".join(cmd).lower()
            name = proc.info.get('name') or ""
            
            if "python" in name.lower() or "celery" in cmd_str or "uvicorn" in cmd_str or "ollama" in name.lower() or "ollama" in cmd_str:
                create_time = datetime.fromtimestamp(proc.info['create_time']).strftime('%Y-%m-%d %H:%M:%S')
                python_processes.append({
                    "pid": proc.info['pid'],
                    "name": name,
                    "create_time": create_time,
                    "cmdline": cmd,
                    "is_self": proc.info['pid'] == current_pid
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
            
    from app.config.settings import settings
    return {
        "current_pid": current_pid,
        "app_file": app.__file__,
        "disable_local_scheduler": settings.DISABLE_LOCAL_SCHEDULER,
        "processes": python_processes
    }


@router.get("/debug/test_placeholder", summary="Run debug test for placeholder generation")
async def debug_test_placeholder(lead_email: str | None = None, campaign_id: str | None = None):
    from app.config.mongodb_config import get_database
    from app.tasks.campaign_tasks import _ai_generate_placeholders, _format_template, _clear_cached_placeholders
    from app.services.llm_manager import LLMManager
    
    db = await get_database()
    
    # Resolve campaign_id dynamically if not provided
    if not campaign_id:
        latest_campaign = await db.campaigns.find_one({}, sort=[("updated_at", -1)])
        if latest_campaign:
            campaign_id = latest_campaign["id"]
            
    # Resolve lead dynamically if not provided
    lead = None
    if lead_email:
        lead = await db.leads.find_one({"email": lead_email})
    elif campaign_id:
        lead = await db.leads.find_one({"campaign_id": campaign_id})
    else:
        lead = await db.leads.find_one({})
        
    if not lead:
        return {"error": "No leads found in the database to run the test."}
        
    campaign = await db.campaigns.find_one({"id": lead["campaign_id"]})
    if not campaign:
        return {"error": f"Campaign not found for lead {lead['id']}"}
        
    body_template = campaign["body_template"]
    lead_name = f"{lead.get('first_name', '')} {lead.get('last_name', '')}".strip()
    
    formatted_body = _format_template(body_template, lead, lead_name, "Shivam", "sriharshith0511@gmail.com")
    
    # Clear cache first
    await _clear_cached_placeholders(campaign["id"], lead["id"])
    
    out = []
    out.append(f"Initial template: {body_template}")
    out.append(f"Formatted before AI: {formatted_body}")
    
    # Let's run the exact system prompt build
    unresolved = ["ai_value_prop"]
    prompt_parts = ["- [ai_value_prop]: Generate a contextually appropriate value for a cold investor outreach email for ElectraWireless (wireless power infrastructure startup, $5M seed round)."]
    
    focus = lead.get("focus", lead.get("custom_fields", {}).get("Focus", ""))
    company = lead.get("company", lead.get("custom_fields", {}).get("Company", ""))
    firm_description = lead.get("custom_fields", {}).get("firm_description", "")
    
    system_msg = f"""You are filling in placeholder values in an email template for investor outreach.

IMPORTANT: You are NOT writing an email. You are ONLY generating values for specific placeholder tokens.
The email template is already written — do not change any other part of it.

LEAD CONTEXT:
- Investor Name: {lead_name}
- Company/Firm: {company}
- Firm Description: {firm_description or "Not available"}
- Primary Investment Focus: {focus or "Not available"}
- ALL Investment Focus Areas: {focus or "Not available"}
- Email: {lead.get('email', '')}

SENDER CONTEXT (ElectraWireless):
- Product: Wireless power infrastructure (5W-30kW range)
- Markets: Smart Kitchens → Industrial → EV charging
- AI Control Layer: Elly (SaaS revenue stream)
- Raising: $5M seed round

Generate ONLY the placeholder values as a JSON object.
- Keys = EXACT placeholder text (without brackets or braces)
- Values = the replacement text (1-2 sentences max, specific and credible)
- For focus area placeholders: MUST use exact text from the investor's focus list above.
Return valid JSON like: {{"Investor Focus Area": "IoT", "Specific Thesis Point": "generated text"}}

PLACEHOLDERS TO FILL:
{chr(10).join(prompt_parts)}"""

    raw_response = "No response"
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
        raw_response = result.get("content", "{}")
        out.append(f"Raw Ollama LLM Response: {raw_response}")
    except Exception as e:
        out.append(f"LLM Call failed: {type(e).__name__} - {str(e)}")
        
    try:
        result_body = await _ai_generate_placeholders(formatted_body, lead, campaign, lead_name, "Shivam")
        out.append(f"Result body after AI: {result_body}")
    except Exception as e:
        out.append(f"Exception raised in safety check: {type(e).__name__} - {str(e)}")
        
    return {"output": out, "raw_response": raw_response}


@router.get("/debug/trigger_pending_tasks", summary="Reschedule all pending tasks to run immediately")
async def debug_trigger_pending_tasks():
    from app.config.mongodb_config import get_database
    from datetime import datetime, timezone
    db = await get_database()
    
    now = datetime.now(timezone.utc)
    res = await db.scheduled_tasks.update_many(
        {"status": "pending"},
        {"$set": {"scheduled_at": now, "updated_at": now}}
    )
    
    return {
        "status": "success",
        "modified_count": res.modified_count,
        "message": f"Rescheduled {res.modified_count} pending tasks to run immediately."
    }


@router.get("/debug/test_limit", summary="Test daily limit counting query")
async def debug_test_limit():
    from app.config.mongodb_config import get_database
    from datetime import datetime, timezone
    db = await get_database()
    
    # Let's count emails sent today using UTC today_start
    today_start_utc = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Let's also try timezone-naive today_start
    today_start_naive = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Let's also check for yesterday (2026-07-12) to see if they match yesterday's start
    yesterday_start_utc = today_start_utc.replace(day=12)
    
    # Query with UTC aware
    count_utc = await db.emails.count_documents({"status": "sent", "sent_at": {"$gte": today_start_utc}})
    count_yesterday_utc = await db.emails.count_documents({"status": "sent", "sent_at": {"$gte": yesterday_start_utc}})
    
    # Query with naive
    count_naive = await db.emails.count_documents({"status": "sent", "sent_at": {"$gte": today_start_naive}})
    
    # Print sample sent email's sent_at type and value
    sample = await db.emails.find_one({"status": "sent"})
    sample_sent_at = sample.get("sent_at") if sample else None
    sample_type = str(type(sample_sent_at)) if sample_sent_at else "None"
    
    # Get all emails count
    total_sent = await db.emails.count_documents({"status": "sent"})
    
    return {
        "today_start_utc": str(today_start_utc),
        "today_start_naive": str(today_start_naive),
        "yesterday_start_utc": str(yesterday_start_utc),
        "count_utc_today": count_utc,
        "count_utc_yesterday": count_yesterday_utc,
        "count_naive_today": count_naive,
        "total_sent": total_sent,
        "sample_sent_at": str(sample_sent_at),
        "sample_sent_at_type": sample_type
    }