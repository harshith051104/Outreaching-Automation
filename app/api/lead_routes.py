"""
Lead API routes.

CRUD for leads plus CSV import and engagement history.
"""

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status

from app.auth.dependencies import get_current_user
from app.schemas.lead import LeadCreate, LeadUpdate, LeadResponse
from app.services.lead_service import (
    create_lead,
    get_leads,
    get_lead,
    update_lead,
    delete_lead,
    import_leads_csv,
    get_lead_engagement,
)

router = APIRouter(prefix="/leads", tags=["Leads"])


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED, summary="Create a lead")
async def create(
    data: LeadCreate,
    current_user: dict = Depends(get_current_user),
):
    """Add a single lead to a campaign."""
    return await create_lead(current_user["id"], data)


@router.get("", summary="List leads")
async def list_leads(
    campaign_id: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
):
    """
    List leads for the current user.

    Optionally filter by campaign_id.
    """
    return await get_leads(campaign_id, current_user["id"], skip=skip, limit=limit)


@router.get("/{lead_id}", response_model=dict, summary="Get lead")
async def get_lead_by_id(
    lead_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get a single lead by ID."""
    return await get_lead(lead_id, current_user["id"])


@router.patch("/{lead_id}", response_model=dict, summary="Update lead")
async def update_lead_route(
    lead_id: str,
    data: dict,
    current_user: dict = Depends(get_current_user),
):
    """
    Update mutable fields of a lead.

    Accepts a partial dict of fields to update.
    """
    return await update_lead(lead_id, current_user["id"], data)


@router.delete("/{lead_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete lead")
async def delete_lead_route(
    lead_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Delete a lead by ID."""
    await delete_lead(lead_id, current_user["id"])


@router.post("/upload-csv", response_model=dict, summary="Upload leads via CSV")
async def upload_csv(
    campaign_id: str = Query(..., description="Campaign ID to import leads into"),
    file: UploadFile = File(..., description="CSV file with lead data"),
    current_user: dict = Depends(get_current_user),
):
    """
    Bulk import leads from a CSV file.

    Supported columns: email, first_name, last_name, company, title, phone, linkedin_url
    """
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a CSV file.",
        )

    content = await file.read()
    return await import_leads_csv(campaign_id, current_user["id"], content)


@router.get("/{lead_id}/engagement", response_model=dict, summary="Get lead engagement history")
async def get_lead_engagement_route(
    lead_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get all tracking events for a lead (opens, clicks, replies)."""
    await get_lead(lead_id, current_user["id"])
    return await get_lead_engagement(lead_id)