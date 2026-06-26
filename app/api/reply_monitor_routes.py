"""
Reply Monitor API routes.

Real-time reply monitoring with WebSocket notifications and draft management.
"""

from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status, Query
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.services.reply_monitor_service import (
    get_pending_replies,
    get_reply_details,
    generate_draft_response,
    approve_draft,
    reject_draft,
    get_monitor_stats,
)
from app.websocket.connection_manager import manager

router = APIRouter(prefix="/reply-monitor", tags=["Reply Monitor"])


@router.get("/replies", summary="Get pending replies")
async def list_pending_replies(
    current_user: dict = Depends(get_current_user),
):
    """Get all unprocessed replies for the current user's campaigns."""
    return await get_pending_replies(current_user["id"])


@router.get("/replies/{reply_id}", summary="Get reply details")
async def get_detail(
    reply_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get full details for a single reply, including lead and campaign info."""
    reply = await get_reply_details(reply_id)
    if not reply:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reply not found")
    return reply


@router.post("/replies/{reply_id}/generate-draft", summary="Generate draft response")
async def generate_draft(
    reply_id: str,
    gmail_account_id: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    """Generate an AI draft response for a reply and store it."""
    try:
        result = await generate_draft_response(reply_id, gmail_account_id)
        await manager.broadcast_draft_ready(current_user["id"], result)
        return result
    except HTTPException as exc:
        raise exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate draft: {exc}",
        )


@router.post("/replies/{reply_id}/approve", summary="Approve and send draft")
async def approve(
    reply_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Approve a draft response and send it via Gmail."""
    try:
        result = await approve_draft(reply_id, current_user["id"])
        await manager.broadcast_draft_sent(current_user["id"], result)
        return result
    except HTTPException as exc:
        raise exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send response: {exc}",
        )


@router.post("/replies/{reply_id}/reject", summary="Reject draft")
async def reject(
    reply_id: str,
    body: Optional[dict] = None,
    current_user: dict = Depends(get_current_user),
):
    """Reject a draft response without sending."""
    reason = (body or {}).get("reason", "")
    return await reject_draft(reply_id, reason)


@router.delete("/replies/{reply_id}", summary="Delete a reply")
async def delete_reply(
    reply_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Delete a reply record entirely."""
    from app.config.mongodb_config import get_database
    db = await get_database()
    result = await db.replies.delete_one({"id": reply_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reply not found")
    return {"status": "deleted"}


@router.get("/stats", summary="Get reply monitor statistics")
async def get_stats(current_user: dict = Depends(get_current_user)):
    """Get aggregated stats for reply monitor."""
    return await get_monitor_stats(current_user["id"])


class UpdateDraftBody(BaseModel):
    subject: str
    body_text: str
    gmail_account_id: Optional[str] = None


@router.patch("/replies/{reply_id}/draft", summary="Update draft response")
async def update_draft(
    reply_id: str,
    body: UpdateDraftBody,
    current_user: dict = Depends(get_current_user),
):
    """Update an existing draft response."""
    from app.config.mongodb_config import get_database
    from datetime import datetime, timezone

    db = await get_database()
    now = datetime.now(timezone.utc)

    update = {
        "$set": {
            "draft_response.subject": body.subject,
            "draft_response.body_text": body.body_text,
            "draft_response.updated_at": now,
        }
    }

    if body.gmail_account_id:
        update["$set"]["gmail_account_id"] = body.gmail_account_id

    result = await db.replies.update_one({"id": reply_id}, update)
    if result.matched_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reply not found")

    return await get_reply_details(reply_id)


@router.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    """
    WebSocket endpoint for real-time reply monitor notifications.

    Connect with: ws://host/api/reply-monitor/ws/{user_id}
    """
    await manager.connect(websocket, user_id)
    try:
        while True:
            try:
                data = await websocket.receive_text()
                if data == "ping":
                    await websocket.send_json({"type": "pong"})
            except Exception:
                break
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        manager.disconnect(websocket, user_id)