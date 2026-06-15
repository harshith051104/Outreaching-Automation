"""
LinkedIn CSV Import API routes.

Handles importing LinkedIn leads from CSV files for outreach campaigns.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, BackgroundTasks
from fastapi.responses import JSONResponse

from app.auth.dependencies import get_current_user
from app.services.linkedin_csv_import_service import (
    import_leads_from_csv,
    get_linkedin_leads_for_outreach,
    bulk_create_linkedin_actions,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/linkedin", tags=["LinkedIn CSV Import"])


@router.post("/import-csv", summary="Import LinkedIn leads from CSV")
async def import_linkedin_csv(
    file: UploadFile = File(...),
    campaign_id: Optional[str] = Query(None, description="Campaign ID to associate leads with"),
    create_leads: bool = Query(True, description="Whether to create lead records"),
    current_user: dict = Depends(get_current_user),
):
    """
    Import LinkedIn leads from a CSV file.
    
    CSV should contain columns for lead information. Supported column names:
    - name, full_name, first_name (person's name)
    - email, email_address (email address)
    - company, company_name (company name)
    - role, job_title, title (job role)
    - linkedin, linkedin_url, profile_url (LinkedIn profile URL)
    - website (company website)
    - notes (additional notes)
    
    At minimum, a LinkedIn URL is required for each lead.
    """
    user_id = current_user["id"]
    
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    
    allowed_extensions = {".csv", ".txt"}
    ext = file.filename.lower().split(".")[-1]
    if f".{ext}" not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"
        )
    
    content = await file.read()
    
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Empty file")
    
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large. Max 10MB.")
    
    logger.info(f"Importing CSV for user {user_id}: {file.filename}")
    
    result = await import_leads_from_csv(
        csv_content=content,
        user_id=user_id,
        campaign_id=campaign_id,
        create_leads=create_leads,
    )
    
    logger.info(f"CSV import complete: {result['valid_leads']} valid leads out of {result['total_rows']} rows")
    
    return {
        "status": "complete",
        "filename": file.filename,
        "total_rows": result["total_rows"],
        "valid_leads": result["valid_leads"],
        "leads_created": result.get("leads_created", 0),
        "leads_updated": result.get("leads_updated", 0),
        "errors": result.get("errors", [])[:20],
    }


@router.post("/import-csv/parse", summary="Parse CSV without creating leads")
async def parse_linkedin_csv(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    """
    Parse a CSV file and return the extracted lead data without creating records.
    
    Useful for previewing CSV data before import.
    """
    user_id = current_user["id"]
    
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    
    content = await file.read()
    
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Empty file")
    
    result = await import_leads_from_csv(
        csv_content=content,
        user_id=user_id,
        create_leads=False,
    )
    
    return {
        "total_rows": result["total_rows"],
        "valid_leads": result["valid_leads"],
        "leads": result["leads"][:50],
        "errors": result.get("errors", [])[:20],
    }


@router.get("/leads", summary="Get LinkedIn leads for outreach")
async def list_linkedin_leads(
    campaign_id: Optional[str] = Query(None, description="Filter by campaign ID"),
    limit: int = Query(100, ge=1, le=500, description="Maximum leads to return"),
    current_user: dict = Depends(get_current_user),
):
    """Get all LinkedIn leads ready for outreach."""
    leads = await get_linkedin_leads_for_outreach(
        user_id=current_user["id"],
        campaign_id=campaign_id,
        limit=limit,
    )
    return {"leads": leads, "count": len(leads)}


@router.post("/leads/bulk-action", summary="Create bulk LinkedIn actions")
async def create_bulk_linkedin_action(
    lead_ids: list[str],
    action_type: str = Query(..., description="Action type: connection_request or send_message"),
    message: Optional[str] = Query(None, description="Message for send_message action"),
    note: Optional[str] = Query(None, description="Note for connection request"),
    current_user: dict = Depends(get_current_user),
):
    """
    Create bulk LinkedIn actions for multiple leads.
    
    Actions will be queued and executed by the scheduler.
    """
    if action_type not in ["connection_request", "send_message"]:
        raise HTTPException(
            status_code=400,
            detail="action_type must be 'connection_request' or 'send_message'"
        )
    
    if action_type == "send_message" and not message:
        raise HTTPException(
            status_code=400,
            detail="message is required for send_message action"
        )
    
    result = await bulk_create_linkedin_actions(
        user_id=current_user["id"],
        lead_ids=lead_ids,
        action_type=action_type,
        message=message,
        note=note,
    )
    
    return result


@router.post("/leads/bulk-connect", summary="Create bulk connection requests")
async def create_bulk_connection_requests(
    lead_ids: list[str],
    note: Optional[str] = Query(None, description="Note to include with connection request"),
    current_user: dict = Depends(get_current_user),
):
    """Create bulk connection request actions for multiple leads."""
    result = await bulk_create_linkedin_actions(
        user_id=current_user["id"],
        lead_ids=lead_ids,
        action_type="connection_request",
        note=note,
    )
    
    return {
        "status": "created",
        "requested": len(lead_ids),
        "created": result["created"],
        "errors": result.get("errors", []),
    }


@router.post("/leads/bulk-message", summary="Create bulk direct messages")
async def create_bulk_messages(
    lead_ids: list[str],
    message: str = Query(..., description="Message to send"),
    current_user: dict = Depends(get_current_user),
):
    """Create bulk direct message actions for multiple leads."""
    if not message or len(message.strip()) < 5:
        raise HTTPException(status_code=400, detail="Message must be at least 5 characters")
    
    result = await bulk_create_linkedin_actions(
        user_id=current_user["id"],
        lead_ids=lead_ids,
        action_type="send_message",
        message=message,
    )
    
    return {
        "status": "created",
        "requested": len(lead_ids),
        "created": result["created"],
        "errors": result.get("errors", []),
    }