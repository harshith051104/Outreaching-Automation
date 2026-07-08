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
    from app.utils.security import sanitize_nosql
    sanitized_data = sanitize_nosql(data)
    # ponytail: sanitize_nosql prevents operator injection
    return await update_lead(lead_id, current_user["id"], sanitized_data)


@router.delete("/{lead_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete lead")
async def delete_lead_route(
    lead_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Delete a lead by ID."""
    await delete_lead(lead_id, current_user["id"])


@router.post("/upload-csv", response_model=dict, summary="Upload leads via CSV/Excel/PDF")
async def upload_csv(
    campaign_id: str = Query(..., description="Campaign ID to import leads into"),
    file: UploadFile = File(..., description="Lead import file (CSV, Excel, or PDF)"),
    current_user: dict = Depends(get_current_user),
):
    """
    Bulk import leads from a CSV, Excel (.xlsx/.xls), or PDF file.

    Supported columns: email, first_name, last_name, company, title, phone, linkedin_url, website, focus
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided.",
        )
        
    filename_lower = file.filename.lower()
    allowed_exts = (".csv", ".xlsx", ".xls", ".pdf")
    if not filename_lower.endswith(allowed_exts):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File must be one of: {', '.join(allowed_exts)}",
        )

    content = await file.read()
    return await import_leads_csv(campaign_id, current_user["id"], content, file.filename)


@router.get("/{lead_id}/engagement", response_model=dict, summary="Get lead engagement history")
async def get_lead_engagement_route(
    lead_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get all tracking events for a lead (opens, clicks, replies)."""
    await get_lead(lead_id, current_user["id"])
    return await get_lead_engagement(lead_id)


from pydantic import BaseModel

class GoogleSheetImportRequest(BaseModel):
    campaign_id: str
    url: str

def extract_google_sheet_csv_url(url: str) -> str:
    """
    ponytail: convert a standard Google Sheets sharing URL into the direct CSV export link.
    """
    import re
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", url)
    if not match:
        raise ValueError("Invalid Google Sheets URL format.")
    spreadsheet_id = match.group(1)
    return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv"


@router.post("/import-google-sheet", summary="Import leads directly from a Google Sheet URL")
async def import_from_google_sheet(
    body: GoogleSheetImportRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Import leads directly from a shared Google Sheets URL.
    The sheet must be accessible (e.g. 'Anyone with link can view' sharing turned on).
    """
    import httpx
    
    try:
        csv_url = extract_google_sheet_csv_url(body.url)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(err)
        )
        
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(csv_url, follow_redirects=True)
            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to fetch Google Sheet. HTTP Status: {response.status_code}. Ensure the sheet sharing is set to 'Anyone with the link can view'."
                )
            content = response.content
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error connecting to Google Sheets: {exc}"
        )
        
    return await import_leads_csv(body.campaign_id, current_user["id"], content, "leads.csv")