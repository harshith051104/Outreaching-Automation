"""
FastAPI AI Routes for metadata-driven agent system.

Provides direct access to agents via both the new orchestrator
(and falls back to original agent implementations).
"""

import asyncio
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/ai", tags=["AI"])


class GenerateEmailRequest(BaseModel):
    lead_id: Optional[str] = None
    campaign_id: Optional[str] = None
    lead_data: Optional[dict] = None
    research_data: Optional[dict] = None
    tone: str = "professional"


class ResearchLeadRequest(BaseModel):
    lead_id: Optional[str] = None
    lead_data: Optional[dict] = None


class ClassifyReplyRequest(BaseModel):
    reply_text: str
    email_id: Optional[str] = None
    original_email: Optional[str] = None
    lead_context: Optional[dict] = None


class GenerateFollowupRequest(BaseModel):
    lead_id: Optional[str] = None
    campaign_id: Optional[str] = None
    previous_email_id: Optional[str] = None
    original_email: Optional[dict] = None
    lead_data: Optional[dict] = None
    sequence_number: Optional[int] = None
    engagement_data: Optional[dict] = None


class CampaignInsightsRequest(BaseModel):
    campaign_id: Optional[str] = None
    campaign_data: Optional[dict] = None
    analytics_data: Optional[dict] = {}


class OrchestratedRequest(BaseModel):
    workflow: str
    inputs: dict


@router.post("/research-lead")
async def ai_research_lead(
    data: ResearchLeadRequest,
    current_user: dict = Depends(get_current_user),
):
    """Research a lead using the Research Agent."""
    try:
        from app.config.mongodb_config import get_database
        db = await get_database()
        
        lead_data = data.lead_data
        if not lead_data and data.lead_id:
            lead = await db.leads.find_one({"id": data.lead_id})
            if lead:
                lead.pop("_id", None)
                lead_data = lead
                
        if not lead_data:
            raise HTTPException(status_code=400, detail="Either lead_id or lead_data must be provided")

        from orchestrator.engine import get_orchestrator
        orchestrator = await get_orchestrator()

        result = await orchestrator.execute_workflow(
            workflow_name="Lead Discovery Workflow",
            inputs={"job_titles": [lead_data.get("role", "")]},
        )
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Research failed: {exc}")


@router.post("/personalize")
async def ai_personalize(
    data: GenerateEmailRequest,
    current_user: dict = Depends(get_current_user),
):
    """Personalize email content using the Personalization Agent."""
    try:
        from app.config.mongodb_config import get_database
        db = await get_database()
        
        lead_data = data.lead_data
        if not lead_data and data.lead_id:
            lead = await db.leads.find_one({"id": data.lead_id})
            if lead:
                lead.pop("_id", None)
                lead_data = lead
                
        if not lead_data:
            raise HTTPException(status_code=400, detail="Either lead_id or lead_data must be provided")

        from app.agents.personalization_agent import personalize_for_lead
        research = data.research_data or {}
        result = await asyncio.to_thread(
            personalize_for_lead, lead_data, research
        )
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Personalization failed: {exc}")


@router.post("/generate-email")
async def ai_generate_email(
    data: GenerateEmailRequest,
    current_user: dict = Depends(get_current_user),
):
    """Generate outreach email using the Email Writer Agent."""
    try:
        from app.config.mongodb_config import get_database
        db = await get_database()
        
        lead_data = data.lead_data
        if not lead_data and data.lead_id:
            lead = await db.leads.find_one({"id": data.lead_id})
            if lead:
                lead.pop("_id", None)
                lead_data = lead
                
        if not lead_data:
            raise HTTPException(status_code=400, detail="Either lead_id or lead_data must be provided")

        if not data.research_data:
            from app.agents.research_agent import research_lead
            from app.agents.personalization_agent import personalize_for_lead

            research = await asyncio.to_thread(research_lead, lead_data)
            personalization = await asyncio.to_thread(
                personalize_for_lead, lead_data, research
            )
        else:
            personalization = data.research_data

        from app.agents.outreach_writer_agent import write_outreach_email

        result = await asyncio.to_thread(
            write_outreach_email,
            lead_data=lead_data,
            personalization_data=personalization,
            tone=data.tone,
        )
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Email generation failed: {exc}")


@router.post("/classify-reply")
async def ai_classify_reply(
    data: ClassifyReplyRequest,
    current_user: dict = Depends(get_current_user),
):
    """Classify email reply using the Reply Classification Agent."""
    try:
        from app.config.mongodb_config import get_database
        db = await get_database()
        
        reply_text = data.reply_text
        original_email = data.original_email or ""
        lead_context = data.lead_context or {}
        
        if not original_email and data.email_id:
            # Fetch from emails collection
            email_doc = await db.emails.find_one({"id": data.email_id})
            if email_doc:
                original_email = email_doc.get("body") or ""
                lead_id = email_doc.get("lead_id")
                if lead_id:
                    lead = await db.leads.find_one({"id": lead_id})
                    if lead:
                        lead.pop("_id", None)
                        lead_context = lead

        from app.agents.reply_classification_agent import classify_reply

        result = await asyncio.to_thread(
            classify_reply,
            reply_text=reply_text,
            original_email=original_email,
            lead_context=lead_context,
            user_id=current_user["id"],
        )
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Classification failed: {exc}")


@router.post("/generate-followup")
async def ai_generate_followup(
    data: GenerateFollowupRequest,
    current_user: dict = Depends(get_current_user),
):
    """Generate follow-up email using the Follow-up Agent."""
    try:
        from app.config.mongodb_config import get_database
        db = await get_database()
        
        lead_data_val = data.lead_data
        if not lead_data_val and data.lead_id:
            lead = await db.leads.find_one({"id": data.lead_id})
            if lead:
                lead.pop("_id", None)
                lead_data_val = lead
                
        if not lead_data_val:
            raise HTTPException(status_code=400, detail="Either lead_id or lead_data must be provided")

        lead_data = dict(lead_data_val)
        if "sender_name" not in lead_data and current_user:
            lead_data["sender_name"] = current_user.get("name", "")

        original_email = data.original_email
        if not original_email and data.previous_email_id:
            email_doc = await db.emails.find_one({"id": data.previous_email_id})
            if email_doc:
                email_doc.pop("_id", None)
                original_email = email_doc
                
        seq_num = data.sequence_number or 2
        eng_data = data.engagement_data or {}

        from app.agents.followup_agent import generate_followup

        result = await asyncio.to_thread(
            generate_followup,
            original_email=original_email,
            lead_data=lead_data,
            sequence_number=seq_num,
            engagement_data=eng_data,
            user_id=current_user["id"],
        )
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Follow-up generation failed: {exc}")


@router.post("/campaign-insights")
async def ai_campaign_insights(
    data: CampaignInsightsRequest,
    current_user: dict = Depends(get_current_user),
):
    """Generate campaign insights using the Analytics Agent."""
    try:
        from app.config.mongodb_config import get_database
        db = await get_database()
        
        campaign_data = data.campaign_data
        analytics_data = data.analytics_data or {}
        
        if not campaign_data and data.campaign_id:
            campaign = await db.campaigns.find_one({"id": data.campaign_id})
            if campaign:
                campaign.pop("_id", None)
                campaign_data = campaign
                # Fetch analytics matching campaign_id
                analytics = await db.campaign_analytics.find_one({"campaign_id": data.campaign_id})
                if analytics:
                    analytics.pop("_id", None)
                    analytics_data = analytics
                    
        if not campaign_data:
            raise HTTPException(status_code=400, detail="Either campaign_id or campaign_data must be provided")

        from app.agents.analytics_agent import generate_campaign_insights as ai_generate_insights

        result = await asyncio.to_thread(
            ai_generate_insights,
            campaign_data=campaign_data,
            analytics_data=analytics_data,
        )
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Insights generation failed: {exc}")


@router.post("/orchestrate")
async def ai_orchestrate(
    data: OrchestratedRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Execute a metadata-driven workflow via the orchestrator.

    This is the primary entry point for the new metadata-driven architecture.
    """
    try:
        from orchestrator.engine import get_orchestrator

        orchestrator = await get_orchestrator()
        result = await orchestrator.execute_workflow(
            workflow_name=data.workflow,
            inputs=data.inputs,
            context={"user_id": current_user.get("id")},
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Workflow execution failed: {exc}")


@router.get("/memory")
async def api_retrieve_memory(
    query: str,
    limit: int = 3,
    campaign_id: str = None,
    current_user: dict = Depends(get_current_user),
):
    """Search vector memory layer for relevant logs using RAG."""
    from app.services.memory_service import AgentMemoryService

    try:
        results = await AgentMemoryService.retrieve_semantic_context(
            query=query,
            limit=limit,
            current_campaign_id=campaign_id,
        )
        return {"status": "success", "results": results}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/agents")
async def list_agents(
    current_user: dict = Depends(get_current_user),
):
    """List all available agents from the metadata registry."""
    try:
        from orchestrator.engine import get_orchestrator

        orchestrator = await get_orchestrator()
        agents = [
            {
                "name": name,
                "role": config.role,
                "purpose": config.purpose,
                "tools": config.tools,
            }
            for name, config in orchestrator.agents.items()
        ]
        return {"agents": agents}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/workflows")
async def list_workflows(
    current_user: dict = Depends(get_current_user),
):
    """List all available workflows from the metadata registry."""
    try:
        from orchestrator.engine import get_orchestrator

        orchestrator = await get_orchestrator()
        workflows = [
            {
                "name": name,
                "description": config.description,
                "agents": config.agents,
                "skills": config.skills,
            }
            for name, config in orchestrator.workflows.items()
        ]
        return {"workflows": workflows}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))