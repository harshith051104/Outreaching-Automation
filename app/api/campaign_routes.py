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
    
    data = {
        "campaigns": campaigns,
        "leads_summary": leads_summary,
        "sample_leads": sample_leads,
        "emails": emails,
        "gmail_accounts": gmail_accounts
    }
    
    # Save to a file in the workspace
    filepath = "c:/Users/sriha/My work/Outreach/ai_outreach_v2_md_agents/scratch/db_dump.json"
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
        
    return PlainTextResponse(f"Saved database dump to {filepath}")