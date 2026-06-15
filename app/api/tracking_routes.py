"""
Tracking API routes.

Public endpoints for email open/click tracking pixels.
No authentication required - these are called by email clients automatically.
"""

from fastapi import APIRouter, Request, Response
from fastapi.responses import Response as FastAPIResponse

from app.services.tracking_service import record_open, record_click, get_tracking_events
from app.utils.email_utils import get_tracking_pixel_bytes

router = APIRouter(tags=["Tracking"])


@router.get(
    "/track/open/{tracking_id}",
    summary="Open tracking pixel",
    description="Returns a 1x1 transparent GIF. Records the open event.",
)
async def track_open(
    tracking_id: str,
    request: Request,
):
    """
    Track an email open event.

    Returns a transparent 1x1 GIF pixel.
    Records: timestamp, IP address, user-agent.
    """
    ip = _get_client_ip(request)
    user_agent = request.headers.get("user-agent", "")

    await record_open(tracking_id, ip, user_agent)

    pixel_bytes = get_tracking_pixel_bytes()
    return Response(
        content=pixel_bytes,
        media_type="image/gif",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, proxy-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@router.get(
    "/track/click/{tracking_id}",
    summary="Click tracking redirect",
    description="Records the click and redirects to the original URL.",
)
async def track_click(
    tracking_id: str,
    url: str,
    request: Request,
):
    """
    Track a link click event and redirect to the destination.

    Args:
        tracking_id: Unique tracking ID for the email.
        url: Base64-encoded original destination URL.
    """
    from urllib.parse import unquote

    original_url = unquote(url)

    ip = _get_client_ip(request)
    user_agent = request.headers.get("user-agent", "")

    await record_click(tracking_id, original_url, ip, user_agent)

    from fastapi import HTTPException, status
    if not original_url or original_url == "None":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing url parameter")

    return FastAPIResponse(
        status_code=status.HTTP_302_FOUND,
        headers={"Location": original_url},
    )


@router.get(
    "/track/attachment/{attachment_id}",
    summary="Track attachment view",
    description="Records that the recipient has viewed/downloaded the tracked attachment.",
)
async def track_attachment(
    attachment_id: str,
    t: str,
    request: Request,
):
    """
    Track an attachment view event.
    """
    from app.tracking.attachment_tracker import record_attachment_view

    ip = _get_client_ip(request)
    user_agent = request.headers.get("user-agent", "")

    await record_attachment_view(attachment_id, t, ip, user_agent)

    return {"status": "success", "attachment_id": attachment_id, "tracked": True}


@router.get("/track/events/{campaign_id}", summary="Get tracking events for campaign")
async def get_events(campaign_id: str):
    """
    Get all tracking events for a campaign.

    Used by analytics to display engagement data.
    """
    return await get_tracking_events(campaign_id)


def _get_client_ip(request: Request) -> str:
    """Extract client IP, checking X-Forwarded-For if behind a proxy."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""