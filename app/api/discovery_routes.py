"""
Lead and Investor Discovery API Routes.

Exposes endpoints to search and discover leads/investors using Apollo, Tavily, and Firecrawl.
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.services.lead_discovery_service import LeadDiscoveryService

router = APIRouter(prefix="/discovery", tags=["Lead Discovery"])
logger = logging.getLogger(__name__)


class DiscoverLeadsRequest(BaseModel):
    campaign_id: str
    query: str
    job_titles: Optional[List[str]] = None
    locations: Optional[List[str]] = None
    industry: Optional[str] = None
    country: Optional[str] = None
    company_size: Optional[str] = None
    funding_stage: Optional[str] = None
    limit: Optional[int] = 10


@router.post("/discover-leads", summary="Discover and import leads with fallback chain")
async def api_discover_leads(
    request: DiscoverLeadsRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Search leads using Apollo, falling back to Tavily and Firecrawl,
    and automatically writing outcomes to MongoDB leads + Qdrant collections.
    """
    service = LeadDiscoveryService()
    try:
        leads = await service.discover_and_store_leads(
            user_id=current_user["id"],
            campaign_id=request.campaign_id,
            query=request.query,
            job_titles=request.job_titles,
            locations=request.locations,
            industry=request.industry,
            country=request.country,
            company_size=request.company_size,
            funding_stage=request.funding_stage,
            limit=request.limit or 10
        )
        
        # Save discovery run history to database
        try:
            import uuid
            from datetime import datetime, timezone
            from app.config.mongodb_config import get_database
            
            db = await get_database()
            run_doc = {
                "id": str(uuid.uuid4()),
                "user_id": current_user["id"],
                "campaign_id": request.campaign_id,
                "query": request.query,
                "job_titles": request.job_titles or [],
                "locations": request.locations or [],
                "industry": request.industry or "",
                "country": request.country or "",
                "company_size": request.company_size or "",
                "funding_stage": request.funding_stage or "",
                "limit": request.limit or 10,
                "leads": leads,
                "count": len(leads),
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            await db.discovery_runs.insert_one(run_doc)
        except Exception as db_exc:
            logger.error("Failed to save discovery run to database: %s", db_exc)

        return {"status": "success", "count": len(leads), "leads": leads}
    except Exception as exc:
        logger.exception("Lead discovery route failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/runs", summary="Get user's previous discovery runs")
async def get_discovery_runs(
    current_user: dict = Depends(get_current_user)
):
    """Retrieve all discovery runs executed by the current user."""
    try:
        from app.config.mongodb_config import get_database
        db = await get_database()
        runs = await db.discovery_runs.find({"user_id": current_user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(length=50)
        return {"status": "success", "runs": runs}
    except Exception as exc:
        logger.exception("Failed to get discovery runs: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))