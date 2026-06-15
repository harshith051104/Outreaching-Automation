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