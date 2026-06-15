"""
Lead list and label API routes.

Manage lead lists, labels, and block list.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.services.lead_list_service import (
    create_lead_list,
    get_lead_lists,
    get_lead_list,
    update_lead_list,
    delete_lead_list,
    create_lead_label,
    get_lead_labels,
    get_lead_label,
    update_lead_label,
    delete_lead_label,
    assign_label_to_leads,
    remove_label_from_leads,
    add_to_block_list,
    get_block_list,
    remove_from_block_list,
)

router = APIRouter(prefix="/leads", tags=["Lead Management"])


class LeadListCreateRequest(BaseModel):
    name: str
    description: str = ""


class LeadListUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None


@router.post("/lists", summary="Create lead list")
async def create_list(
    data: LeadListCreateRequest,
    current_user: dict = Depends(get_current_user),
):
    """Create a new lead list."""
    return await create_lead_list(current_user["id"], data.name, data.description)


@router.get("/lists", summary="List lead lists")
async def list_lists(
    current_user: dict = Depends(get_current_user),
):
    """Get all lead lists for the current user."""
    return await get_lead_lists(current_user["id"])


@router.get("/lists/{list_id}", summary="Get lead list")
async def get_list(
    list_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get a single lead list."""
    return await get_lead_list(list_id, current_user["id"])


@router.patch("/lists/{list_id}", summary="Update lead list")
async def update_list(
    list_id: str,
    data: LeadListUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    """Update a lead list."""
    update_data = data.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")
    return await update_lead_list(list_id, current_user["id"], update_data)


@router.delete("/lists/{list_id}", summary="Delete lead list")
async def delete_list(
    list_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Delete a lead list."""
    deleted = await delete_lead_list(list_id, current_user["id"])
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead list not found")
    return {"status": "deleted", "list_id": list_id}


class LeadLabelCreateRequest(BaseModel):
    name: str
    color: str = "#3B82F6"
    description: str = ""


class LeadLabelUpdateRequest(BaseModel):
    name: str | None = None
    color: str | None = None
    description: str | None = None


class LabelAssignRequest(BaseModel):
    lead_ids: list[str]


@router.post("/labels", summary="Create lead label")
async def create_label(
    data: LeadLabelCreateRequest,
    current_user: dict = Depends(get_current_user),
):
    """Create a new lead label."""
    return await create_lead_label(current_user["id"], data.name, data.color, data.description)


@router.get("/labels", summary="List lead labels")
async def list_labels(
    current_user: dict = Depends(get_current_user),
):
    """Get all lead labels for the current user."""
    return await get_lead_labels(current_user["id"])


@router.get("/labels/{label_id}", summary="Get lead label")
async def get_label(
    label_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get a single lead label."""
    label = await get_lead_label(label_id, current_user["id"])
    if not label:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Label not found")
    return label


@router.patch("/labels/{label_id}", summary="Update lead label")
async def update_label(
    label_id: str,
    data: LeadLabelUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    """Update a lead label."""
    update_data = data.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")
    result = await update_lead_label(label_id, current_user["id"], update_data)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Label not found")
    return result


@router.delete("/labels/{label_id}", summary="Delete lead label")
async def delete_label(
    label_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Delete a lead label."""
    deleted = await delete_lead_label(label_id, current_user["id"])
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Label not found")
    return {"status": "deleted", "label_id": label_id}


@router.post("/labels/{label_id}/assign", summary="Assign label to leads")
async def assign_label(
    label_id: str,
    data: LabelAssignRequest,
    current_user: dict = Depends(get_current_user),
):
    """Assign a label to multiple leads."""
    count = await assign_label_to_leads(label_id, data.lead_ids, current_user["id"])
    return {"status": "assigned", "leads_updated": count}


@router.post("/labels/{label_id}/unassign", summary="Remove label from leads")
async def unassign_label(
    label_id: str,
    data: LabelAssignRequest,
    current_user: dict = Depends(get_current_user),
):
    """Remove a label from multiple leads."""
    count = await remove_label_from_leads(label_id, data.lead_ids, current_user["id"])
    return {"status": "removed", "leads_updated": count}


class BlockListCreateRequest(BaseModel):
    value: str
    reason: str = ""


@router.post("/block-list", summary="Add to block list")
async def block_add(
    data: BlockListCreateRequest,
    current_user: dict = Depends(get_current_user),
):
    """Add an email or domain to the block list."""
    return await add_to_block_list(current_user["id"], data.value, data.reason)


@router.get("/block-list", summary="List block list")
async def block_list(
    current_user: dict = Depends(get_current_user),
):
    """Get all block list entries."""
    return await get_block_list(current_user["id"])


@router.delete("/block-list/{entry_id}", summary="Remove from block list")
async def block_remove(
    entry_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Remove an entry from the block list."""
    deleted = await remove_from_block_list(entry_id, current_user["id"])
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")
    return {"status": "removed", "entry_id": entry_id}