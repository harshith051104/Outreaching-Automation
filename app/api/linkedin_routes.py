"""
LinkedIn Content Strategy & Outreach API Routes.

Exposes endpoints for:
- Content calendar generation (existing)
- LinkedIn session management
- Profile research (via workflow)
- Connection requests (via workflow)
- Messages and follow-ups (via workflow)
- Approval workflow
- Conversations
- Analytics (via existing tracking_events)
- Action history

All outreach operations call WorkflowExecutor — no business logic in routes.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.config.mongodb_config import get_database
from app.utils.id_generator import generate_id

router = APIRouter(prefix="/linkedin", tags=["LinkedIn"])
logger = logging.getLogger(__name__)


@router.get("/test/debug")
async def test_debug():
    import traceback
    try:
        from app.config.groq_config import get_llm_section_disabled, set_llm_section_disabled
        val = get_llm_section_disabled("linkedin")
        return {"status": "ok", "val": val}
    except Exception as e:
        return {"status": "error", "traceback": traceback.format_exc()}


@router.get("/test/errors", summary="Get last failed actions")
async def get_test_errors():
    db = await get_database()
    cursor = db.linkedin_actions.find({})
    actions = []
    async for act in cursor:
        actions.append({
            "id": act.get("id"),
            "status": act.get("status"),
            "updated_at": str(act.get("updated_at")),
            "error": act.get("error"),
            "action_type": act.get("action_type")
        })
    return {"count": len(actions), "actions": actions}



@router.get("/test/reset", summary="Reset all action statuses to pending_approval")
async def reset_action_status():
    db = await get_database()
    result = await db.linkedin_actions.update_many(
        {},
        {"$set": {"status": "pending_approval"}}
    )
    return {"status": "success", "modified_count": result.modified_count, "matched_count": result.matched_count}



@router.get("/test/all_actions")
async def get_all_actions():
    db = await get_database()
    cursor = db.linkedin_actions.find({})
    actions = []
    async for act in cursor:
        act_copy = dict(act)
        act_copy.pop("_id", None)
        # Convert datetime objects to string
        for k, v in act_copy.items():
            if isinstance(v, datetime):
                act_copy[k] = v.isoformat()
        actions.append(act_copy)
    return {"count": len(actions), "actions": actions}


@router.get("/test/approve/{action_id}", summary="Test approve action without auth")
async def test_approve_action(action_id: str):
    db = await get_database()
    
    from bson import ObjectId
    from bson.errors import InvalidId

    action_query = {}
    try:
        action_query["$or"] = [{"id": action_id}, {"_id": ObjectId(action_id)}]
    except InvalidId:
        action_query["id"] = action_id

    action = await db.linkedin_actions.find_one(action_query)
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")

        
    action_type = action.get("action_type")
    linkedin_url = action.get("linkedin_url", "")
    message = action.get("message", "")
    user_id = action.get("user_id")

    if action.get("status") not in ("pending_approval", "failed", "rejected"):
        raise HTTPException(status_code=400, detail=f"Action is already {action.get('status')}")

    try:
        if action_type == "connection_request":
            from app.services.linkedin_outreach_service import send_connection_request
            result = await send_connection_request(linkedin_url, message, user_id)
        elif action_type in ("first_message", "message", "followup"):
            from app.services.linkedin_outreach_service import send_message
            result = await send_message(linkedin_url, message, user_id)
        else:
            result = {"success": False, "error": f"Unknown action type: {action_type}"}

        new_status = "executed" if result.get("success") else "failed"
        update_fields = {
            "status": new_status,
            "execution_result": result,
            "executed_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        if result.get("success") and action_type == "connection_request":
            if result.get("note_sent") is False or not message:
                update_fields["message_skipped"] = True

        await db.linkedin_actions.update_one(
            action_query,
            {"$set": update_fields}
        )
        return {"status": "success", "action_status": new_status, "result": result}
    except Exception as exc:
        import traceback
        tb = traceback.format_exc()
        logger.exception("Action execution failed: %s", exc)
        await db.linkedin_actions.update_one(
            action_query,
            {"$set": {"status": "failed", "error": f"{str(exc)}\n{tb}", "updated_at": datetime.now(timezone.utc)}}
        )
        raise HTTPException(status_code=500, detail=f"Action execution failed: {str(exc)}\n{tb}")


@router.get("/test/action/{action_id}", summary="Get full action document")
async def test_get_action(action_id: str):
    db = await get_database()
    
    from bson import ObjectId
    from bson.errors import InvalidId

    action_query = {}
    try:
        action_query["$or"] = [{"id": action_id}, {"_id": ObjectId(action_id)}]
    except InvalidId:
        action_query["id"] = action_id

    action = await db.linkedin_actions.find_one(action_query)
    if action:
        action.pop("_id", None)
    return action








# ── Request/Response Models ────────────────────────────────────────────────


class GenerateCalendarRequest(BaseModel):
    campaign_id: str = ""
    campaign_goal: str
    target_audience: str
    industry: str


class ResearchRequest(BaseModel):
    linkedin_url: str
    outreach_type: str = "connection_request"


class ConnectionRequest(BaseModel):
    linkedin_url: str
    lead_id: str = ""
    custom_note: str = ""


class FollowProfileRequest(BaseModel):
    linkedin_url: str
    lead_id: str = ""



class MessageRequest(BaseModel):
    linkedin_url: str
    lead_id: str = ""
    message_type: str = "first_message"
    custom_message: str = ""


class FollowupRequest(BaseModel):
    linkedin_url: str
    lead_id: str = ""
    lead_name: str = ""
    lead_company: str = ""
    lead_role: str = ""
    sequence_number: int = 1


class EditActionRequest(BaseModel):
    message: str


class CreateCampaignRequest(BaseModel):
    name: str
    description: str = ""
    goal: str = ""
    target_audience: str = ""
    daily_connection_limit: int = 20
    daily_message_limit: int = 50


# ── Content Calendar (Existing) ────────────────────────────────────────────


@router.post("/generate-calendar", summary="Run strategic CrewAI content calendar generator")
async def generate_calendar(
    request: GenerateCalendarRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Kicks off the Content Strategy sequential Crew to formulate content pillars
    and write a 30-day posting calendar.
    """
    try:
        from app.agents.content_strategy_agent import generate_linkedin_calendar
        content_doc = await generate_linkedin_calendar(
            user_id=current_user["id"],
            campaign_id=request.campaign_id,
            campaign_goal=request.campaign_goal,
            target_audience=request.target_audience,
            industry=request.industry
        )
        return {"status": "success", "content_calendar": content_doc}
    except Exception as exc:
        logger.exception("Failed to generate LinkedIn Content Calendar: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/calendars", summary="Get user's generated content calendars")
async def get_calendars(
    current_user: dict = Depends(get_current_user)
):
    """Retrieve all calendars generated by the user."""
    db = await get_database()
    calendars = await db.content.find({"user_id": current_user["id"]}, {"_id": 0}).to_list(length=50)
    return {"status": "success", "calendars": calendars}




class ImportCookiesRequest(BaseModel):
    cookies: list[dict]


@router.post("/session/import-cookies", summary="Import LinkedIn cookies")
async def import_cookies(request: ImportCookiesRequest, current_user: dict = Depends(get_current_user)):
    """Import and validate LinkedIn session cookies."""
    from app.services.linkedin_outreach_service import import_session_with_cookies
    result = await import_session_with_cookies(current_user["id"], request.cookies)
    return result


@router.post("/session/connect", summary="Start LinkedIn browser session")
async def connect_session(current_user: dict = Depends(get_current_user)):
    """Launch Playwright browser for LinkedIn login."""
    from app.services.linkedin_outreach_service import start_session
    result = await start_session(current_user["id"])
    return result


@router.get("/session/status", summary="Get LinkedIn session status")
async def session_status(current_user: dict = Depends(get_current_user)):
    """Check if LinkedIn session is active."""
    from app.services.linkedin_outreach_service import get_session_status
    result = await get_session_status(current_user["id"])
    return result


@router.post("/session/validate", summary="Validate LinkedIn session and update details")
async def validate_user_session(current_user: dict = Depends(get_current_user)):
    """Manually validate session to refresh account name and avatar."""
    from app.services.linkedin_outreach_service import validate_session
    result = await validate_session(current_user["id"])
    return result



@router.post("/session/disconnect", summary="Clear LinkedIn session")
async def disconnect_session(current_user: dict = Depends(get_current_user)):
    """Remove stored session cookies."""
    from app.services.linkedin_outreach_service import disconnect_session as _disconnect
    result = await _disconnect(current_user["id"])
    return result


# ── Research ───────────────────────────────────────────────────────────────


@router.post("/research", summary="Research a LinkedIn profile")
async def research_profile(
    request: ResearchRequest,
    current_user: dict = Depends(get_current_user)
):
    """Execute LinkedIn Research workflow: scrape profile → web research → personalize."""
    from orchestrator.engine import get_orchestrator

    try:
        orchestrator = await get_orchestrator()
        result = await orchestrator.execute_workflow(
            "LinkedIn Research Workflow",
            inputs={
                "linkedin_url": request.linkedin_url,
                "user_id": current_user["id"],
                "outreach_type": request.outreach_type,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            context={"user_id": current_user["id"]},
        )
        return {"status": "success", **result}
    except Exception as exc:
        logger.exception("LinkedIn research failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/outreach/follow", summary="Generate follow profile/company draft")
async def create_follow_request(
    request: FollowProfileRequest,
    current_user: dict = Depends(get_current_user)
):
    """Create a follow profile/company action directly in pending_approval status."""
    db = await get_database()
    action_id = generate_id()
    action_doc = {
        "id": action_id,
        "user_id": current_user["id"],
        "lead_id": request.lead_id,
        "linkedin_url": request.linkedin_url,
        "action_type": "follow_profile",
        "status": "pending_approval",
        "message": "Follow profile/company",
        "created_at": datetime.now(timezone.utc),
    }
    await db.linkedin_actions.insert_one(action_doc)
    return {
        "status": "success",
        "action_id": action_id,
        "status_text": "pending_approval"
    }


@router.post("/outreach/connection", summary="Generate connection request draft")
async def create_connection_request(
    request: ConnectionRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """Create a connection request draft using the LinkedIn Connection Workflow, or save custom note directly."""
    db = await get_database()
    
    try:
        # If user explicitly provided a custom note, bypass the orchestrator workflow
        if request.custom_note:
            action_id = generate_id()
            action_doc = {
                "id": action_id,
                "user_id": current_user["id"],
                "lead_id": request.lead_id,
                "linkedin_url": request.linkedin_url,
                "action_type": "connection_request",
                "status": "pending_approval",
                "message": request.custom_note,
                "created_at": datetime.now(timezone.utc),
            }
            await db.linkedin_actions.insert_one(action_doc)
            return {
                "status": "success",
                "action_id": action_id,
                "draft_message": request.custom_note,
                "status_text": "pending_approval"
            }
            
        # Otherwise, run the full LinkedIn Connection Workflow asynchronously in the background
        from orchestrator.engine import get_orchestrator
        
        action_id = generate_id()
        
        async def run_workflow_bg():
            try:
                orchestrator = await get_orchestrator()
                await orchestrator.execute_workflow(
                    "LinkedIn Connection Workflow",
                    inputs={
                        "action_id": action_id,
                        "linkedin_url": request.linkedin_url,
                        "user_id": current_user["id"],
                        "lead_id": request.lead_id or "",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                    context={"user_id": current_user["id"]},
                )
                logger.info("LinkedIn Connection Workflow finished in background for %s", request.linkedin_url)
            except Exception as e:
                logger.exception("Background LinkedIn Connection Workflow failed: %s", e)

        background_tasks.add_task(run_workflow_bg)
        
        return {
            "status": "processing",
            "action_id": action_id,
            "draft_message": "Analyzing profile and drafting connection note in background...",
            "status_text": "processing"
        }
    except Exception as exc:
        logger.exception("Connection request creation failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/outreach/message", summary="Generate message draft")
async def create_message(
    request: MessageRequest,
    current_user: dict = Depends(get_current_user)
):
    """Generate a LinkedIn message draft via the orchestrator."""
    from orchestrator.engine import get_orchestrator

    try:
        orchestrator = await get_orchestrator()
        # Use the message agent handler directly
        result = await orchestrator._agent_linkedin_message({
            "lead_data": {"linkedin_url": request.linkedin_url},
            "personalization_data": {},
            "message_type": request.message_type,
            "conversation_history": [],
        })

        # Save as draft
        db = await get_database()
        action_doc = {
            "id": generate_id(),
            "user_id": current_user["id"],
            "lead_id": request.lead_id,
            "linkedin_url": request.linkedin_url,
            "action_type": request.message_type,
            "status": "pending_approval",
            "message": result.get("message_text", request.custom_message or ""),
            "created_at": datetime.now(timezone.utc),
        }
        await db.linkedin_actions.insert_one(action_doc)
        action_doc.pop("_id", None)

        return {"status": "success", "action": action_doc, "generated": result}
    except Exception as exc:
        logger.exception("Message generation failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/outreach/followup", summary="Generate follow-up draft")
async def create_followup(
    request: FollowupRequest,
    current_user: dict = Depends(get_current_user)
):
    """Execute LinkedIn Followup workflow to generate a follow-up draft."""
    from orchestrator.engine import get_orchestrator

    try:
        orchestrator = await get_orchestrator()
        result = await orchestrator.execute_workflow(
            "LinkedIn Followup Workflow",
            inputs={
                "linkedin_url": request.linkedin_url,
                "user_id": current_user["id"],
                "lead_id": request.lead_id,
                "lead_name": request.lead_name,
                "lead_company": request.lead_company,
                "lead_role": request.lead_role,
                "sequence_number": request.sequence_number,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            context={"user_id": current_user["id"]},
        )
        return {"status": "success", **result}
    except Exception as exc:
        logger.exception("Followup workflow failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ── Approval Workflow ──────────────────────────────────────────────────────


@router.get("/outreach/pending", summary="List pending approval actions")
async def list_pending_actions(current_user: dict = Depends(get_current_user)):
    """List all LinkedIn actions awaiting user approval."""
    db = await get_database()
    actions = await db.linkedin_actions.find(
        {"user_id": current_user["id"], "status": {"$in": ["pending_approval", "failed"]}},
        {"_id": 0}
    ).sort("created_at", -1).to_list(length=100)
    return {"status": "success", "actions": actions, "count": len(actions)}


@router.post("/outreach/approve/{action_id}", summary="Approve and execute action")
async def approve_action(
    action_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Approve a pending action and execute it via Playwright."""
    db = await get_database()
    
    from bson import ObjectId
    from bson.errors import InvalidId

    action_query = {"user_id": current_user["id"]}
    try:
        action_query["$or"] = [{"id": action_id}, {"_id": ObjectId(action_id)}]
    except InvalidId:
        action_query["id"] = action_id

    action = await db.linkedin_actions.find_one(action_query)

    if not action:
        raise HTTPException(status_code=404, detail="Action not found")


    if action.get("status") not in ("pending_approval", "failed", "rejected"):
        raise HTTPException(status_code=400, detail=f"Action is already {action.get('status')}")

    action_type = action.get("action_type")
    linkedin_url = action.get("linkedin_url", "")
    message = action.get("message", "")

    try:
        if action_type == "email":
            from app.services.email_service import send_campaign_email
            email_id = action.get("email_id")
            if email_id and message:
                await db.emails.update_one(
                    {"id": email_id},
                    {"$set": {"body_html": message, "updated_at": datetime.now(timezone.utc)}}
                )
            sent_email = await send_campaign_email(email_id)
            result = {"success": True, "result": sent_email}
        elif action_type == "connection_request":
            from app.services.linkedin_outreach_service import send_connection_request
            result = await send_connection_request(linkedin_url, message, current_user["id"])
        elif action_type in ("first_message", "message", "followup"):
            target = linkedin_url or ""
            if "linkedin.com" in target or target.startswith("http"):
                from app.services.linkedin_outreach_service import send_message
                result = await send_message(target, message, current_user["id"])
            else:
                from app.services.linkedin_outreach_service import send_message_by_name
                result = await send_message_by_name(target, message, current_user["id"])
        elif action_type in ("follow", "follow_profile"):
            from app.services.linkedin_outreach_service import follow_profile
            result = await follow_profile(linkedin_url, current_user["id"])
        else:
            result = {"success": False, "error": f"Unknown action type: {action_type}"}

        new_status = "executed" if result.get("success") else "failed"
        update_fields = {
            "status": new_status,
            "execution_result": result,
            "executed_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        if result.get("success") and action_type == "connection_request":
            if result.get("note_sent") is False or not message:
                update_fields["message_skipped"] = True

        await db.linkedin_actions.update_one(
            action_query,
            {"$set": update_fields}
        )


        # Increment daily count on success
        if result.get("success") and action_type != "email":
            from app.services.linkedin_scheduler_service import increment_daily_count
            await increment_daily_count(
                current_user["id"],
                "connection" if action_type == "connection_request" else "message"
            )

            # Update relationship stage
            stage = "connection_sent" if action_type == "connection_request" else "message_sent"
            await db.linkedin_relationships.update_one(
                {"user_id": current_user["id"], "linkedin_url": linkedin_url},
                {
                    "$set": {"current_stage": stage, "updated_at": datetime.now(timezone.utc)},
                    "$push": {"stage_history": {"stage": stage, "timestamp": datetime.now(timezone.utc)}},
                    "$setOnInsert": {"id": generate_id(), "created_at": datetime.now(timezone.utc)},
                },
                upsert=True,
            )

            # Record tracking event
            await db.tracking_events.insert_one({
                "id": generate_id(),
                "user_id": current_user["id"],
                "event_type": f"linkedin_{stage}",
                "linkedin_url": linkedin_url,
                "channel": "linkedin",
                "timestamp": datetime.now(timezone.utc),
            })

        return {"status": "success", "action_status": new_status, "result": result}

    except Exception as exc:
        import traceback
        tb = traceback.format_exc()
        error_msg = str(exc)
        try:
            logger.exception("Action execution failed: %s", exc)
        except Exception:
            print(f"Action execution failed: {error_msg}\n{tb}")
        try:
            await db.linkedin_actions.update_one(
                action_query,
                {"$set": {"status": "failed", "error": f"{error_msg}\n{tb}", "updated_at": datetime.now(timezone.utc)}}
            )
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Action execution failed: {error_msg}")


@router.post("/outreach/reject/{action_id}", summary="Reject a pending action")
async def reject_action(
    action_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Reject a pending action and remove it."""
    db = await get_database()
    
    from bson import ObjectId
    from bson.errors import InvalidId

    action_query = {
        "user_id": current_user["id"],
        "status": {"$in": ["pending_approval", "failed"]}
    }
    try:
        action_query["$or"] = [{"id": action_id}, {"_id": ObjectId(action_id)}]
    except InvalidId:
        action_query["id"] = action_id

    action = await db.linkedin_actions.find_one(action_query)
    if not action:
        raise HTTPException(status_code=404, detail="Action not found or not pending")

    result = await db.linkedin_actions.update_one(
        action_query,
        {"$set": {"status": "rejected", "updated_at": datetime.now(timezone.utc)}}
    )
    
    if action.get("action_type") == "email":
        email_id = action.get("email_id")
        if email_id:
            await db.emails.update_one(
                {"id": email_id},
                {"$set": {"status": "rejected", "updated_at": datetime.now(timezone.utc)}}
            )

    return {"status": "success", "action_id": action_id, "new_status": "rejected"}


@router.put("/outreach/edit/{action_id}", summary="Edit a draft message")
async def edit_action(
    action_id: str,
    request: EditActionRequest,
    current_user: dict = Depends(get_current_user)
):
    """Edit the message of a pending action before approval."""
    db = await get_database()
    
    from bson import ObjectId
    from bson.errors import InvalidId

    action_query = {
        "user_id": current_user["id"],
        "status": {"$in": ["pending_approval", "failed", "rejected"]}
    }
    try:
        action_query["$or"] = [{"id": action_id}, {"_id": ObjectId(action_id)}]
    except InvalidId:
        action_query["id"] = action_id

    action = await db.linkedin_actions.find_one(action_query)
    if not action:
        raise HTTPException(status_code=404, detail="Action not found or not pending")

    result = await db.linkedin_actions.update_one(
        action_query,
        {"$set": {"message": request.message, "updated_at": datetime.now(timezone.utc)}}
    )
    
    if action.get("action_type") == "email":
        email_id = action.get("email_id")
        if email_id:
            await db.emails.update_one(
                {"id": email_id},
                {"$set": {"body_html": request.message, "updated_at": datetime.now(timezone.utc)}}
            )

    return {"status": "success", "action_id": action_id, "message": request.message}



class RescheduleActionRequest(BaseModel):
    execute_at: str  # ISO timestamp

@router.post("/outreach/reschedule/{action_id}", summary="Reschedule a pending or failed action")
async def reschedule_action_route(
    action_id: str,
    request: RescheduleActionRequest,
    current_user: dict = Depends(get_current_user)
):
    """Reschedule an outreach action."""
    from app.services.linkedin_scheduler_service import schedule_action
    
    try:
        execute_dt = datetime.fromisoformat(request.execute_at.replace("Z", "+00:00"))
    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {val_err}")
        
    res = await schedule_action(action_id, execute_dt, current_user["id"])
    if not res.get("scheduled"):
        raise HTTPException(status_code=404, detail=res.get("error", "Action not found"))
    return {"status": "success", "action_id": action_id, "scheduled_at": request.execute_at}



# ── Campaigns ──────────────────────────────────────────────────────────────


@router.post("/campaigns", summary="Create a LinkedIn campaign")
async def create_campaign(
    request: CreateCampaignRequest,
    current_user: dict = Depends(get_current_user)
):
    """Create a new LinkedIn outreach campaign."""
    db = await get_database()
    campaign = {
        "id": generate_id(),
        "user_id": current_user["id"],
        "name": request.name,
        "description": request.description,
        "goal": request.goal,
        "target_audience": request.target_audience,
        "daily_connection_limit": request.daily_connection_limit,
        "daily_message_limit": request.daily_message_limit,
        "status": "draft",
        "total_planned_actions": 0,
        "executed_actions": 0,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    await db.linkedin_campaigns.insert_one(campaign)
    campaign.pop("_id", None)
    return {"status": "success", "campaign": campaign}


@router.get("/campaigns", summary="List LinkedIn campaigns")
async def list_campaigns(current_user: dict = Depends(get_current_user)):
    """List all LinkedIn campaigns for the user."""
    db = await get_database()
    campaigns = await db.linkedin_campaigns.find(
        {"user_id": current_user["id"]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(length=50)
    return {"status": "success", "campaigns": campaigns}


@router.post("/campaigns/{campaign_id}/start", summary="Start a LinkedIn campaign")
async def start_campaign(
    campaign_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Execute LinkedIn Campaign workflow."""
    from orchestrator.engine import get_orchestrator

    try:
        orchestrator = await get_orchestrator()
        result = await orchestrator.execute_workflow(
            "LinkedIn Campaign Workflow",
            inputs={
                "campaign_id": campaign_id,
                "user_id": current_user["id"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            context={"user_id": current_user["id"]},
        )
        return {"status": "success", **result}
    except Exception as exc:
        logger.exception("Campaign start failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/campaigns/{campaign_id}/pause", summary="Pause a LinkedIn campaign")
async def pause_campaign(
    campaign_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Pause an active campaign."""
    db = await get_database()
    result = await db.linkedin_campaigns.update_one(
        {"id": campaign_id, "user_id": current_user["id"]},
        {"$set": {"status": "paused", "updated_at": datetime.now(timezone.utc)}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return {"status": "success", "campaign_id": campaign_id, "new_status": "paused"}


# ── Conversations ──────────────────────────────────────────────────────────


@router.get("/conversations", summary="List LinkedIn conversations")
async def list_conversations(current_user: dict = Depends(get_current_user)):
    """List all LinkedIn conversations."""
    db = await get_database()
    conversations = await db.linkedin_conversations.find(
        {"user_id": current_user["id"]},
        {"_id": 0}
    ).sort("last_message_at", -1).to_list(length=50)
    return {"status": "success", "conversations": conversations}


@router.get("/conversations/{contact_id}", summary="Get conversation thread")
async def get_conversation(
    contact_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get full conversation thread with a contact."""
    db = await get_database()
    conversation = await db.linkedin_conversations.find_one(
        {"user_id": current_user["id"], "contact_linkedin_url": contact_id},
        {"_id": 0}
    )
    if not conversation:
        # Try by ID
        conversation = await db.linkedin_conversations.find_one(
            {"user_id": current_user["id"], "id": contact_id},
            {"_id": 0}
        )
    return {"status": "success", "conversation": conversation or {}}


# ── Analytics ──────────────────────────────────────────────────────────────


@router.get("/analytics", summary="Get LinkedIn outreach analytics")
async def get_analytics(current_user: dict = Depends(get_current_user)):
    """Get LinkedIn analytics from existing tracking_events system."""
    from orchestrator.engine import get_orchestrator

    try:
        orchestrator = await get_orchestrator()
        result = await orchestrator._agent_linkedin_analytics({
            "user_id": current_user["id"]
        })
        return {"status": "success", **result}
    except Exception as exc:
        logger.exception("LinkedIn analytics failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ── Relationships ──────────────────────────────────────────────────────────


@router.get("/relationships", summary="List relationship statuses")
async def list_relationships(current_user: dict = Depends(get_current_user)):
    """List all LinkedIn relationship stages."""
    db = await get_database()
    relationships = await db.linkedin_relationships.find(
        {"user_id": current_user["id"]},
        {"_id": 0}
    ).sort("updated_at", -1).to_list(length=100)

    for rel in relationships:
        lead_id = rel.get("lead_id")
        linkedin_url = rel.get("linkedin_url", "")
        if not rel.get("first_name"):
            lead = None
            if lead_id:
                lead = await db.leads.find_one({"id": lead_id})
            if not lead and linkedin_url:
                lead = await db.leads.find_one({
                    "user_id": current_user["id"],
                    "$or": [{"linkedin": linkedin_url}, {"linkedin_url": linkedin_url}]
                })
            if lead:
                rel["first_name"] = lead.get("first_name", "")
                rel["last_name"] = lead.get("last_name", "")
                rel["contact_name"] = f"{lead.get('first_name', '')} {lead.get('last_name', '')}".strip() or None

    return {"status": "success", "relationships": relationships}


# ── History ────────────────────────────────────────────────────────────────


@router.get("/history", summary="Get LinkedIn outreach action history")
async def get_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """Paginated list of all LinkedIn outreach actions."""
    db = await get_database()
    query = {"user_id": current_user["id"]}
    if status:
        query["status"] = status

    total = await db.linkedin_actions.count_documents(query)
    skip = (page - 1) * page_size

    actions = await db.linkedin_actions.find(
        query, {"_id": 0}
    ).sort("created_at", -1).skip(skip).limit(page_size).to_list(length=page_size)

    return {
        "status": "success",
        "actions": actions,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


# ── Queue Status ───────────────────────────────────────────────────────────


@router.get("/queue", summary="Get LinkedIn action queue status")
async def get_queue_status(current_user: dict = Depends(get_current_user)):
    """Get the status of the user's LinkedIn action queue and daily limits."""
    from app.services.linkedin_scheduler_service import get_queue_status as _get_status
    result = await _get_status(current_user["id"])
    return {"status": "success", **result}


# ── Settings LLM Toggle ───────────────────────────────────────────────────

class ToggleLLMRequest(BaseModel):
    disabled: bool
    section: str = "linkedin"

@router.get("/settings/llm", summary="Get LLM disabled status")
async def get_llm_status(
    section: str = "linkedin",
    current_user: dict = Depends(get_current_user)
):
    """Get the status of the LLM toggle."""
    from app.config.groq_config import get_llm_section_disabled
    return {
        "disabled": get_llm_section_disabled(section),
        "section": section
    }

@router.post("/settings/llm", summary="Toggle LLM usage")
async def toggle_llm_status(
    request: ToggleLLMRequest,
    current_user: dict = Depends(get_current_user)
):
    """Toggle LLM usage between real API calls and mock responses."""
    from app.config.groq_config import set_llm_section_disabled
    db = await get_database()
    
    # Update section config
    set_llm_section_disabled(request.section, request.disabled)
    
    # Persist in DB
    await db.system_settings.update_one(
        {"key": f"disable_llm_{request.section}"},
        {"$set": {
            "value": request.disabled,
            "updated_at": datetime.now(timezone.utc)
        }},
        upsert=True
    )
    
    return {
        "status": "success",
        "disabled": request.disabled,
        "section": request.section
    }


# ── Settings Auto-Reply Toggle ─────────────────────────────────────────────

class ToggleAutoReplyRequest(BaseModel):
    enabled: bool

@router.get("/settings/auto-reply", summary="Get auto-reply setting status")
async def get_auto_reply_status(
    current_user: dict = Depends(get_current_user)
):
    """Get the auto-reply setting status for the current user."""
    db = await get_database()
    uid = current_user["id"]
    setting = await db.system_settings.find_one({"key": f"linkedin_auto_reply_{uid}"})
    enabled = setting.get("value", True) if setting else True
    return {"enabled": enabled}

@router.post("/settings/auto-reply", summary="Toggle auto-reply setting")
async def toggle_auto_reply(
    request: ToggleAutoReplyRequest,
    current_user: dict = Depends(get_current_user)
):
    """Toggle auto-reply draft generation."""
    db = await get_database()
    uid = current_user["id"]
    await db.system_settings.update_one(
        {"key": f"linkedin_auto_reply_{uid}"},
        {"$set": {
            "value": request.enabled,
            "updated_at": datetime.now(timezone.utc)
        }},
        upsert=True
    )
    return {"status": "success", "enabled": request.enabled}