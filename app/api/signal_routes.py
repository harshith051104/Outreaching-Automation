"""
Signal Intelligence API Routes.

Exposes endpoints to gather recent news, hiring signals, and pricing adjustments.
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.services.signal_service import SignalService
from app.config.mongodb_config import get_database

router = APIRouter(prefix="/signals", tags=["Signal Intelligence"])
logger = logging.getLogger(__name__)


class GatherSignalsRequest(BaseModel):
    lead_id: str
    company_name: str
    website_url: Optional[str] = None


@router.post("/gather", summary="Query Tavily & Firecrawl to gather expansion and hiring signals")
async def gather_signals(
    request: GatherSignalsRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Search and scrape recent signals, log them in MongoDB and index in Qdrant.
    """
    service = SignalService()
    try:
        signals = await service.gather_and_store_signals(
            lead_id=request.lead_id,
            company_name=request.company_name,
            website_url=request.website_url
        )
        return {"status": "success", "count": len(signals), "signals": signals}
    except Exception as exc:
        logger.exception("Failed to gather signals: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/lead/{lead_id}", summary="Get signals logged for a specific lead")
async def get_lead_signals(
    lead_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Retrieve all signals stored for a given lead ID."""
    db = await get_database()
    signals = await db.signals.find({"lead_id": lead_id}, {"_id": 0}).to_list(length=100)
    return {"status": "success", "signals": signals}


class EvaluateOpportunityRequest(BaseModel):
    lead_id: str


@router.post("/opportunity", summary="Evaluate sales opportunity and best contact for a lead")
async def evaluate_lead_opportunity(
    request: EvaluateOpportunityRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Evaluate the sales opportunity based on signals and research,
    storing urgency, best target contact, recommended offer, and confidence score.
    """
    service = SignalService()
    try:
        opp = await service.evaluate_opportunity(lead_id=request.lead_id)
        return {"status": "success", "opportunity": opp}
    except Exception as exc:
        logger.exception("Failed to evaluate opportunity: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/opportunity/lead/{lead_id}", summary="Get opportunity stored for a specific lead")
async def get_lead_opportunity(
    lead_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Retrieve opportunity details for a given lead ID."""
    db = await get_database()
    opp = await db.opportunities.find_one({"lead_id": lead_id}, {"_id": 0})
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity evaluation not found for this lead")
    return {"status": "success", "opportunity": opp}


@router.get("", summary="Get all signals for the user's leads")
async def get_all_signals(
    current_user: dict = Depends(get_current_user)
):
    """Retrieve all signals stored for all leads belonging to the user."""
    db = await get_database()
    leads = await db.leads.find({"user_id": current_user["id"]}, {"id": 1}).to_list(length=1000)
    
    # Ensure every lead dictionary has an 'id' key
    for l in leads:
        if "id" not in l and "_id" in l:
            l["id"] = str(l["_id"])
            
    lead_ids = [l["id"] for l in leads]
    signals = await db.signals.find({"lead_id": {"$in": lead_ids}}, {"_id": 0}).to_list(length=1000)
    return {"status": "success", "signals": signals}


@router.get("/opportunities", summary="Get all opportunity evaluations for user's leads")
async def get_all_opportunities(
    current_user: dict = Depends(get_current_user)
):
    """Retrieve all opportunity evaluations for all leads belonging to the user."""
    db = await get_database()
    leads = await db.leads.find(
        {"user_id": current_user["id"]},
        {"id": 1, "name": 1, "company": 1, "email": 1, "role": 1}
    ).to_list(length=1000)
    
    # Ensure every lead dictionary has an 'id' key
    for l in leads:
        if "id" not in l and "_id" in l:
            l["id"] = str(l["_id"])
            
    lead_map = {l["id"]: l for l in leads}
    lead_ids = list(lead_map.keys())
    opps = await db.opportunities.find({"lead_id": {"$in": lead_ids}}, {"_id": 0}).to_list(length=1000)
    
    for opp in opps:
        opp["lead"] = lead_map.get(opp["lead_id"])
        
    return {"status": "success", "opportunities": opps}