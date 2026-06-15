"""
Campaign Flow Builder API Routes.

Exposes REST endpoints to manage templates (save/load nodes/edges) and
trigger/monitor background workflow executions (runs, step states, logs, approvals).
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.config.mongodb_config import get_database
from app.services.flow_execution_service import FlowExecutionService

router = APIRouter(prefix="/flows", tags=["Flow Builder"])
logger = logging.getLogger(__name__)


class FlowSaveRequest(BaseModel):
    name: str
    description: Optional[str] = ""
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]


class ApprovalRequest(BaseModel):
    approved: bool


@router.get("", summary="List all campaign flows")
async def list_flows(current_user: dict = Depends(get_current_user)):
    db = await get_database()
    flows = await db.campaign_flows.find({"user_id": current_user["id"]}, {"_id": 0}).to_list(length=100)
    return flows


@router.post("", summary="Create a new flow template")
async def create_flow(request: FlowSaveRequest, current_user: dict = Depends(get_current_user)):
    import uuid
    db = await get_database()
    flow_id = str(uuid.uuid4())
    
    flow_doc = {
        "id": flow_id,
        "user_id": current_user["id"],
        "name": request.name,
        "description": request.description,
        "nodes": request.nodes,
        "edges": request.edges,
        "status": "draft",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.campaign_flows.insert_one(flow_doc)
    return flow_doc


@router.get("/{flow_id}", summary="Get a flow template by ID")
async def get_flow(flow_id: str, current_user: dict = Depends(get_current_user)):
    db = await get_database()
    flow = await db.campaign_flows.find_one({"id": flow_id, "user_id": current_user["id"]}, {"_id": 0})
    if not flow:
        raise HTTPException(status_code=404, detail="Campaign flow not found")
    return flow


@router.put("/{flow_id}", summary="Update flow template canvas nodes and edges")
async def update_flow(flow_id: str, request: FlowSaveRequest, current_user: dict = Depends(get_current_user)):
    db = await get_database()
    
    flow = await db.campaign_flows.find_one({"id": flow_id, "user_id": current_user["id"]})
    if not flow:
        raise HTTPException(status_code=404, detail="Campaign flow not found")
        
    await db.campaign_flows.update_one(
        {"id": flow_id},
        {
            "$set": {
                "name": request.name,
                "description": request.description,
                "nodes": request.nodes,
                "edges": request.edges,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
        }
    )
    return {"status": "success", "message": "Flow canvas saved successfully."}


@router.delete("/{flow_id}", summary="Delete a flow template")
async def delete_flow(flow_id: str, current_user: dict = Depends(get_current_user)):
    db = await get_database()
    res = await db.campaign_flows.delete_one({"id": flow_id, "user_id": current_user["id"]})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Flow not found")
    # Also delete run history
    await db.flow_runs.delete_many({"flow_id": flow_id})
    return {"status": "success", "message": "Flow template and related execution history deleted."}


@router.post("/{flow_id}/publish", summary="Activate/Publish campaign flow")
async def publish_flow(flow_id: str, current_user: dict = Depends(get_current_user)):
    db = await get_database()
    flow = await db.campaign_flows.find_one({"id": flow_id, "user_id": current_user["id"]})
    if not flow:
        raise HTTPException(status_code=404, detail="Campaign flow not found")
        
    await db.campaign_flows.update_one(
        {"id": flow_id},
        {
            "$set": {
                "status": "active",
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
        }
    )
    return {"status": "success", "message": "Flow published successfully.", "flow_status": "active"}


@router.post("/{flow_id}/pause", summary="Pause an active campaign flow")
async def pause_flow(flow_id: str, current_user: dict = Depends(get_current_user)):
    db = await get_database()
    flow = await db.campaign_flows.find_one({"id": flow_id, "user_id": current_user["id"]})
    if not flow:
        raise HTTPException(status_code=404, detail="Campaign flow not found")
        
    await db.campaign_flows.update_one(
        {"id": flow_id},
        {
            "$set": {
                "status": "draft",
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
        }
    )
    return {"status": "success", "message": "Flow set to draft/paused.", "flow_status": "draft"}


@router.post("/{flow_id}/trigger", summary="Manually trigger workflow execution")
async def trigger_flow(flow_id: str, current_user: dict = Depends(get_current_user)):
    try:
        res = await FlowExecutionService.start_flow(flow_id, current_user["id"], is_manual=True)
        return res
    except Exception as e:
        logger.exception("Failed to start manual flow execution: %s", e)
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{flow_id}/runs", summary="Get execution runs history for a flow template")
async def get_flow_runs(flow_id: str, current_user: dict = Depends(get_current_user)):
    db = await get_database()
    runs = await db.flow_runs.find({"flow_id": flow_id, "user_id": current_user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(length=100)
    return runs


@router.get("/runs/{run_id}", summary="Get execution run details + logs + context")
async def get_run_details(run_id: str, current_user: dict = Depends(get_current_user)):
    db = await get_database()
    run = await db.flow_runs.find_one({"id": run_id, "user_id": current_user["id"]}, {"_id": 0})
    if not run:
        raise HTTPException(status_code=404, detail="Execution run details not found")
    return run


@router.post("/runs/{run_id}/approve", summary="Approve a waiting approval node step")
async def approve_run(run_id: str, request: ApprovalRequest, current_user: dict = Depends(get_current_user)):
    try:
        await FlowExecutionService.approve_run_step(run_id, request.approved)
        return {"status": "success", "message": f"Step action response handled: approved={request.approved}"}
    except Exception as e:
        logger.exception("Failed to handle step approval: %s", e)
        raise HTTPException(status_code=400, detail=str(e))
