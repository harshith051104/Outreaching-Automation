"""
Gmail API routes.

Handles OAuth2 flow, account management, email sending, and inbox reading.
"""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from starlette.responses import RedirectResponse

from app.auth.dependencies import get_current_user
from app.services.gmail_service import (
    get_auth_url,
    handle_callback,
    get_gmail_accounts,
    send_email,
    get_inbox_messages,
    get_thread_messages,
)
from app.config.mongodb_config import get_database
from app.config.settings import settings

router = APIRouter(prefix="/gmail", tags=["Gmail"])


class SendEmailRequest(BaseModel):
    gmail_account_id: str
    to: str
    subject: str
    body_html: str
    thread_id: str | None = None


class GmailAccountResponse(BaseModel):
    id: str
    email: str
    is_active: bool
    name: str = ""


class UpdateGmailAccountRequest(BaseModel):
    name: str


@router.get("/auth", summary="Start Gmail OAuth flow")
async def start_auth(current_user: dict = Depends(get_current_user)):
    """
    Generate a Google OAuth2 authorization URL.

    Redirects the user to Google's consent screen.
    """
    auth_url, state = await get_auth_url(current_user["id"])
    return {"authorization_url": auth_url, "state": state}


@router.get("/callback", summary="Gmail OAuth callback")
async def callback(code: str = Query(...), state: str | None = Query(None)):
    """
    Handle the OAuth2 callback from Google.
    """
    try:
        await handle_callback(code, state)
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/dashboard/gmail?status=connected",
            status_code=302,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to connect Gmail account: {exc}",
        )


@router.get("/accounts", response_model=list[GmailAccountResponse], summary="List connected Gmail accounts")
async def list_accounts(current_user: dict = Depends(get_current_user)):
    """Return all Gmail accounts connected by the current user."""
    accounts = await get_gmail_accounts(current_user["id"])
    return [GmailAccountResponse(**a) for a in accounts]


@router.post("/send", summary="Send email")
async def send(
    data: SendEmailRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Send an email via a connected Gmail account.

    Injects tracking pixel and rewrites links automatically.
    """
    result = await send_email(
        gmail_account_id=data.gmail_account_id,
        to=data.to,
        subject=data.subject,
        body_html=data.body_html,
        thread_id=data.thread_id,
    )
    return result


@router.get("/inbox/{account_id}", summary="Get inbox messages")
async def inbox(
    account_id: str,
    max_results: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    """Fetch the latest inbox messages for a Gmail account."""
    return await get_inbox_messages(account_id, max_results)


@router.get("/thread/{account_id}/{thread_id}", summary="Get thread messages")
async def get_thread(
    account_id: str,
    thread_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Retrieve all messages in a Gmail thread."""
    return await get_thread_messages(account_id, thread_id)


@router.delete("/accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Disconnect Gmail account")
async def disconnect(
    account_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Disconnect (deactivate) a connected Gmail account."""
    db = await get_database()
    result = await db.gmail_accounts.update_one(
        {"id": account_id, "user_id": current_user["id"]},
        {"$set": {"is_active": False}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found.")
    return None


@router.put("/accounts/{account_id}", summary="Update Gmail account settings")
async def update_account_name(
    account_id: str,
    data: UpdateGmailAccountRequest,
    current_user: dict = Depends(get_current_user),
):
    """Update display name for a connected Gmail account."""
    db = await get_database()
    result = await db.gmail_accounts.update_one(
        {"id": account_id, "user_id": current_user["id"]},
        {"$set": {"name": data.name, "updated_at": datetime.now(timezone.utc)}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found.")
    return {"status": "success"}