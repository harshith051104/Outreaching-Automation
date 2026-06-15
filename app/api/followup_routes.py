"""
Follow-up API routes.

Management of scheduled follow-up emails.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth.dependencies import get_current_user
from app.services.followup_service import (
    get_pending_followups,
    get_followups,
    execute_followup,
    cancel_followup,
)

router = APIRouter(prefix="/followups", tags=["Follow-ups"])


@router.get("", summary="List follow-ups")
async def list_followups(
    campaign_id: str | None = Query(None),
    lead_id: str | None = Query(None),
    status: str | None = Query(None),
    current_user: dict = Depends(get_current_user),
):
    """
    List follow-up tasks with optional filtering by campaign, lead, and status.
    """
    return await get_followups(
        current_user["id"], campaign_id, lead_id, status
    )



@router.post("/{followup_id}/execute", summary="Execute follow-up")
async def execute(
    followup_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Execute a pending follow-up immediately.

    Generates the follow-up content and sends it via Gmail.
    """
    try:
        result = await execute_followup(followup_id)
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute follow-up: {exc}",
        )


@router.put("/{followup_id}/cancel", summary="Cancel follow-up")
async def cancel(
    followup_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Cancel a pending follow-up task.

    Only pending follow-ups can be cancelled.
    """
    try:
        result = await cancel_followup(followup_id)
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel follow-up: {exc}",
        )