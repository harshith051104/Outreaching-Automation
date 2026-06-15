"""
Contact Enrichment API Routes.

Exposes endpoints to enrich contacts and verify email deliverability via Hunter.io.
"""

import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr

from app.auth.dependencies import get_current_user
from app.services.hunter_enrichment_service import HunterEnrichmentService
from app.config.mongodb_config import get_database

router = APIRouter(prefix="/enrichment", tags=["Contact Enrichment"])
logger = logging.getLogger(__name__)


class VerifyEmailRequest(BaseModel):
    email: EmailStr
    lead_id: str


@router.post("/verify-lead-email", summary="Verify lead email deliverability using Hunter")
async def verify_lead_email(
    request: VerifyEmailRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Check if a lead's email is deliverable and save the enrichment output to MongoDB.
    """
    service = HunterEnrichmentService()
    db = await get_database()

    lead = await db.leads.find_one({"id": request.lead_id, "user_id": current_user["id"]})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    try:
        verification = await service.verify_email(request.email)
        
        await db.leads.update_one(
            {"id": request.lead_id},
            {
                "$set": {
                    "enrichment_data.email_verification": verification,
                    "updated_at": datetime.now(timezone.utc) if 'datetime' in globals() else None
                }
            }
        )

        return {"status": "success", "verification": verification}
    except Exception as exc:
        logger.exception("Email enrichment failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))