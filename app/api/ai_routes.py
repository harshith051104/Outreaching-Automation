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
    lead_data: dict
    research_data: Optional[dict] = None
    tone: str = "professional"


class ResearchLeadRequest(BaseModel):
    lead_data: dict


class ClassifyReplyRequest(BaseModel):
    reply_text: str
    original_email: str
    lead_context: dict


class GenerateFollowupRequest(BaseModel):
    original_email: dict
    lead_data: dict
    sequence_number: int
    engagement_data: dict


class CampaignInsightsRequest(BaseModel):
    campaign_data: dict
    analytics_data: dict = {}


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
        from orchestrator.engine import get_orchestrator
        orchestrator = await get_orchestrator()

        result = await orchestrator.execute_workflow(
            workflow_name="Lead Discovery Workflow",
            inputs={"job_titles": [data.lead_data.get("role", "")]},
        )
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Research failed: {exc}")


@router.post("/personalize")
async def ai_personalize(
    data: GenerateEmailRequest,
    current_user: dict = Depends(get_current_user),
):
    """Personalize email content using the Personalization Agent."""
    try:
        from app.agents.personalization_agent import personalize_for_lead

        research = data.research_data or {}
        result = await asyncio.to_thread(
            personalize_for_lead, data.lead_data, research
        )
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Personalization failed: {exc}")


@router.post("/generate-email")
async def ai_generate_email(
    data: GenerateEmailRequest,
    current_user: dict = Depends(get_current_user),
):
    """Generate outreach email using the Email Writer Agent."""
    try:
        if not data.research_data:
            from app.agents.research_agent import research_lead
            from app.agents.personalization_agent import personalize_for_lead

            research = await asyncio.to_thread(research_lead, data.lead_data)
            personalization = await asyncio.to_thread(
                personalize_for_lead, data.lead_data, research
            )
        else:
            personalization = data.research_data

        from app.agents.outreach_writer_agent import write_outreach_email

        result = await asyncio.to_thread(
            write_outreach_email,
            lead_data=data.lead_data,
            personalization_data=personalization,
            tone=data.tone,
        )
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Email generation failed: {exc}")


@router.post("/classify-reply")
async def ai_classify_reply(
    data: ClassifyReplyRequest,
    current_user: dict = Depends(get_current_user),
):
    """Classify email reply using the Reply Classification Agent."""
    try:
        from app.agents.reply_classification_agent import classify_reply

        result = await asyncio.to_thread(
            classify_reply,
            reply_text=data.reply_text,
            original_email=data.original_email,
            lead_context=data.lead_context,
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
        from app.agents.followup_agent import generate_followup

        lead_data = dict(data.lead_data)
        if "sender_name" not in lead_data and current_user:
            lead_data["sender_name"] = current_user.get("name", "")

        result = await asyncio.to_thread(
            generate_followup,
            original_email=data.original_email,
            lead_data=lead_data,
            sequence_number=data.sequence_number,
            engagement_data=data.engagement_data,
        )
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Follow-up generation failed: {exc}")


@router.post("/campaign-insights")
async def ai_campaign_insights(
    data: CampaignInsightsRequest,
    current_user: dict = Depends(get_current_user),
):
    """Generate campaign insights using the Analytics Agent."""
    try:
        from app.agents.analytics_agent import generate_campaign_insights as ai_generate_insights

        result = await asyncio.to_thread(
            ai_generate_insights,
            campaign_data=data.campaign_data,
            analytics_data=data.analytics_data,
        )
        return result
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