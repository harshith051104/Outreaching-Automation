"""
Webhook API routes.

Manage webhook subscriptions and view delivery events.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.services.webhook_service import (
    create_webhook,
    get_webhooks,
    get_webhook,
    update_webhook,
    delete_webhook,
    get_webhook_events,
    get_webhook_event_stats,
    get_available_event_types,
)

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


class WebhookCreateRequest(BaseModel):
    url: str
    events: list[str]
    secret: Optional[str] = None


class WebhookUpdateRequest(BaseModel):
    url: Optional[str] = None
    events: Optional[list[str]] = None
    is_active: Optional[bool] = None
    secret: Optional[str] = None


@router.post("", summary="Create webhook")
async def create(
    data: WebhookCreateRequest,
    current_user: dict = Depends(get_current_user),
):
    """Create a new webhook subscription."""
    return await create_webhook(
        user_id=current_user["id"],
        url=data.url,
        events=data.events,
        secret=data.secret,
    )


@router.get("", summary="List webhooks")
async def list_all(
    current_user: dict = Depends(get_current_user),
):
    """List all webhooks for the current user."""
    return await get_webhooks(current_user["id"])


@router.get("/event-types", summary="List available event types")
async def event_types():
    """Get all available webhook event types."""
    return get_available_event_types()


@router.get("/{webhook_id}", summary="Get webhook")
async def get_one(
    webhook_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get a single webhook by ID."""
    webhook = await get_webhook(webhook_id, current_user["id"])
    if not webhook:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")
    return webhook


@router.patch("/{webhook_id}", summary="Update webhook")
async def update(
    webhook_id: str,
    data: WebhookUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    """Update a webhook subscription."""
    update_data = data.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")

    result = await update_webhook(webhook_id, current_user["id"], update_data)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")
    return result


@router.delete("/{webhook_id}", summary="Delete webhook")
async def delete(
    webhook_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Delete a webhook subscription."""
    deleted = await delete_webhook(webhook_id, current_user["id"])
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")
    return {"status": "deleted", "webhook_id": webhook_id}


@router.get("/{webhook_id}/events", summary="Get webhook events")
async def events(
    webhook_id: str,
    limit: int = 50,
    current_user: dict = Depends(get_current_user),
):
    """Get delivery events for a specific webhook."""
    return await get_webhook_events(webhook_id=webhook_id, limit=limit)


@router.get("/{webhook_id}/stats", summary="Get webhook event stats")
async def stats(
    webhook_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get aggregate delivery stats for a webhook."""
    return await get_webhook_event_stats(webhook_id)