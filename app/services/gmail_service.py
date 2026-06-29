"""
Gmail service layer.

Handles OAuth flow, email sending, inbox reading, and reply checking
through the Google Gmail API. All DB operations are async via Motor.
"""

import base64
import logging
import secrets
from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import HTTPException, status
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.exceptions import RefreshError

from app.config.mongodb_config import get_database
from app.config.settings import settings
from app.config.gmail_config import build_gmail_service, refresh_credentials
from app.utils.id_generator import generate_id

logger = logging.getLogger(__name__)

# OAuth sessions are now persisted in MongoDB (collection: `oauth_sessions`)
# to survive application server reloads and restarts.



@asynccontextmanager
async def handle_gmail_exceptions(account_id: str):
    """Context manager to catch Google Auth errors, mark the account inactive, and raise 401."""
    try:
        yield
    except RefreshError as exc:
        logger.error("Gmail credentials expired or revoked for account %s: %s", account_id, exc)
        db = await get_database()
        await db.gmail_accounts.update_one(
            {"id": account_id},
            {"$set": {"is_active": False, "connection_error": "Token has been expired or revoked."}}
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Gmail account disconnected. Please reconnect your Gmail account in settings."
        )


# ---------------------------------------------------------------------------
# OAuth helpers
# ---------------------------------------------------------------------------

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


async def _get_google_credentials(user_id: str | None = None) -> tuple[str, str]:
    """Retrieve Google OAuth credentials. Only the .env values work."""
    return settings.GOOGLE_CLIENT_ID, settings.GOOGLE_CLIENT_SECRET


async def _build_flow(state: str | None = None, user_id: str | None = None) -> Flow:
    """Build a Google OAuth2 flow from configured client credentials."""
    client_id, client_secret = await _get_google_credentials(user_id)
    
    client_config = {
        "web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.GOOGLE_REDIRECT_URI],
        }
    }
    flow = Flow.from_client_config(client_config, scopes=SCOPES, state=state)
    flow.redirect_uri = settings.GOOGLE_REDIRECT_URI
    return flow


async def _load_gmail_account(gmail_account_id: str) -> dict:
    """Load a Gmail account document from DB, raising 404 if missing."""
    db = await get_database()
    account = await db.gmail_accounts.find_one({"id": gmail_account_id})
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gmail account not found.",
        )
    return account


async def _build_service(account: dict):
    """Build an authenticated Gmail API service from a stored account."""
    client_id, client_secret = await _get_google_credentials(account.get("user_id"))

    creds = Credentials(
        token=account["access_token"],
        refresh_token=account.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
    )

    # Refresh if expired
    if creds.expired and creds.refresh_token:
        refreshed = refresh_credentials({
            "access_token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_uri": creds.token_uri,
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "scopes": creds.scopes,
        })
        # Persist refreshed tokens
        db = await get_database()
        await db.gmail_accounts.update_one(
            {"id": account["id"]},
            {
                "$set": {
                    "access_token": refreshed["access_token"],
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )
        creds.token = refreshed["access_token"]

    return build_gmail_service({
        "access_token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": creds.scopes,
    })


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def get_auth_url(user_id: str) -> tuple:
    """
    Generate an OAuth2 authorization URL and state token.

    Returns (authorization_url, state).
    The state is our custom session_id that Google passes back in the callback.
    """
    flow = await _build_flow(user_id=user_id)

    # Generate a session ID — this will be the OAuth `state` parameter so
    # Google returns it in the callback and we can look up the user_id.
    session_id = secrets.token_urlsafe(32)

    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=session_id,  # Pass our session_id as the state to Google
    )

    # Extract the code_verifier generated for PKCE
    code_verifier = getattr(flow, "code_verifier", None)

    # Store user_id keyed by the session_id in MongoDB
    db = await get_database()
    await db.oauth_sessions.update_one(
        {"state": session_id},
        {"$set": {
            "user_id": user_id, 
            "code_verifier": code_verifier,
            "created_at": datetime.now(timezone.utc)
        }},
        upsert=True
    )
    logger.info("OAuth session created for user %s with state %s", user_id, session_id)

    return authorization_url, session_id


async def handle_callback(code: str, state: str | None) -> dict:
    """
    Exchange the OAuth2 authorization code for tokens and store the Gmail account.

    State contains the session_id for session lookup.
    """
    if not state:
        raise ValueError("OAuth state is missing. Please try connecting your Gmail account again.")

    db = await get_database()
    session = await db.oauth_sessions.find_one_and_delete({"state": state})
    if not session:
        raise ValueError(
            "OAuth session expired or invalid. Please try connecting your Gmail account again."
        )

    user_id = session["user_id"]

    # Rebuild the flow for token exchange (no need to store the flow object)
    flow = await _build_flow(state=state, user_id=user_id)
    
    # Restore the code_verifier for PKCE if it exists
    code_verifier = session.get("code_verifier")
    if code_verifier:
        flow.code_verifier = code_verifier
        
    flow.fetch_token(code=code)
    credentials = flow.credentials

    client_id, client_secret = await _get_google_credentials(user_id)

    # Build a temporary service to fetch the user's email address
    service = build_gmail_service({
        "access_token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": client_id,
        "client_secret": client_secret,
        "scopes": SCOPES,
    })
    profile = service.users().getProfile(userId="me").execute()
    gmail_email = profile.get("emailAddress", "")

    db = await get_database()

    # Upsert: if this gmail address is already connected for this user, update tokens
    now = datetime.now(timezone.utc)
    existing = await db.gmail_accounts.find_one(
        {"user_id": user_id, "email": gmail_email}
    )

    account_doc = {
        "user_id": user_id,
        "email": gmail_email,
        "access_token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_expiry": credentials.expiry.isoformat() if credentials.expiry else None,
        "is_active": True,
        "updated_at": now,
        "name": gmail_email.split("@")[0].replace(".", " ").replace("_", " ").title(),
    }

    if existing:
        await db.gmail_accounts.update_one(
            {"id": existing["id"]}, {"$set": account_doc}
        )
        account_doc["id"] = existing["id"]
    else:
        account_doc["id"] = generate_id()
        account_doc["created_at"] = now
        await db.gmail_accounts.insert_one(account_doc)

    logger.info("Gmail account %s connected for user %s", gmail_email, user_id)

    return {
        "id": account_doc["id"],
        "email": gmail_email,
        "is_active": True,
    }


async def get_gmail_accounts(user_id: str) -> list:
    """Return all connected Gmail accounts for a user."""
    db = await get_database()
    cursor = db.gmail_accounts.find(
        {"user_id": user_id, "is_active": True},
        {"_id": 0, "access_token": 0, "refresh_token": 0, "token_expiry": 0},
    )
    return await cursor.to_list(length=100)


async def send_email(
    gmail_account_id: str,
    to: str,
    subject: str,
    body_html: str,
    thread_id: Optional[str] = None,
    in_reply_to: Optional[str] = None,
    references: Optional[str] = None,
    attachments: Optional[list] = None,
) -> dict:
    """
    Send an email via the Gmail API.

    For replies, pass thread_id + in_reply_to + references to continue
    the existing Gmail thread (RFC 2822 compliant threading).

    Args:
        thread_id: Gmail thread ID — threads the message in Gmail's UI.
        in_reply_to: Message-ID of the email being replied to (RFC 2822).
        references: Space-separated list of ancestor Message-IDs (RFC 2822).
        attachments: List of dicts with 'filename', 'content', 'content_type' keys

    Returns a dict with message id and thread id from the Gmail response.
    """
    async with handle_gmail_exceptions(gmail_account_id):
        account = await _load_gmail_account(gmail_account_id)
        service = await _build_service(account)

        if attachments:
            # Use mixed for attachments
            msg = MIMEMultipart("mixed")
        else:
            msg = MIMEMultipart("alternative")

        from email.utils import formataddr
        msg["To"] = to
        if account.get("name"):
            msg["From"] = formataddr((account["name"], account["email"]))
        else:
            msg["From"] = account["email"]
        msg["Subject"] = subject

        # RFC 2822 threading headers — makes the reply appear in the same thread
        if in_reply_to:
            msg["In-Reply-To"] = in_reply_to
        if references:
            msg["References"] = references
        elif in_reply_to:
            # If no explicit references chain, use in_reply_to as the references
            msg["References"] = in_reply_to

        # Add HTML body
        msg.attach(MIMEText(body_html, "html"))

        # Add attachments if provided
        if attachments:
            for att in attachments:
                att_content = att.get("content", b"")
                att_filename = att.get("filename", "file")
                att_content_type = att.get("content_type", "application/octet-stream")

                # If content is base64 encoded string, decode it
                if isinstance(att_content, str):
                    att_content = base64.b64decode(att_content)

                from email.mime.base import MIMEBase
                from email.encoders import encode_base64
                part = MIMEBase("application", "octet-stream")
                part.set_payload(att_content)
                encode_base64(part)
                part.add_header("Content-Disposition", f"attachment; filename={att_filename}")
                msg.attach(part)

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
        body_payload: dict = {"raw": raw}
        if thread_id:
            body_payload["threadId"] = thread_id

        result = (
            service.users().messages().send(userId="me", body=body_payload).execute()
        )

        return {
            "gmail_message_id": result.get("id"),
            "gmail_thread_id": result.get("threadId"),
            "label_ids": result.get("labelIds", []),
        }


async def get_inbox_messages(
    gmail_account_id: str, max_results: int = 20
) -> list:
    """Fetch the latest inbox messages for a connected Gmail account."""
    async with handle_gmail_exceptions(gmail_account_id):
        account = await _load_gmail_account(gmail_account_id)
        service = await _build_service(account)

        results = (
            service.users()
            .messages()
            .list(userId="me", labelIds=["INBOX"], maxResults=max_results)
            .execute()
        )

        messages = []
        for msg_ref in results.get("messages", []):
            msg = (
                service.users()
                .messages()
                .get(userId="me", id=msg_ref["id"], format="metadata")
                .execute()
            )
            headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
            messages.append(
                {
                    "id": msg["id"],
                    "thread_id": msg.get("threadId"),
                    "subject": headers.get("Subject", ""),
                    "from": headers.get("From", ""),
                    "date": headers.get("Date", ""),
                    "snippet": msg.get("snippet", ""),
                }
            )

        return messages


async def get_thread_messages(
    gmail_account_id: str, thread_id: str
) -> list:
    """Retrieve all messages within a Gmail thread."""
    async with handle_gmail_exceptions(gmail_account_id):
        account = await _load_gmail_account(gmail_account_id)
        service = await _build_service(account)

        thread = (
            service.users()
            .threads()
            .get(userId="me", id=thread_id, format="full")
            .execute()
        )

        messages = []
        for msg in thread.get("messages", []):
            headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
            # Extract body text
            body_text = ""
            payload = msg.get("payload", {})
            if payload.get("body", {}).get("data"):
                body_text = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")
            elif payload.get("parts"):
                for part in payload["parts"]:
                    if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
                        body_text = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")
                        break

            messages.append(
                {
                    "id": msg["id"],
                    "thread_id": msg.get("threadId"),
                    "subject": headers.get("Subject", ""),
                    "from": headers.get("From", ""),
                    "to": headers.get("To", ""),
                    "date": headers.get("Date", ""),
                    "body": body_text,
                    "snippet": msg.get("snippet", ""),
                }
            )

        return messages


async def check_for_replies(
    gmail_account_id: str, thread_ids: list
) -> list:
    """
    Check a list of Gmail threads for new replies (messages beyond the first).

    Returns a list of reply dicts for threads that have more than one message.
    """
    async with handle_gmail_exceptions(gmail_account_id):
        account = await _load_gmail_account(gmail_account_id)
        service = await _build_service(account)

        replies = []
        for tid in thread_ids:
            try:
                thread = (
                    service.users()
                    .threads()
                    .get(userId="me", id=tid, format="metadata")
                    .execute()
                )
                thread_messages = thread.get("messages", [])
                if len(thread_messages) > 1:
                    # Everything after the first message is considered a reply
                    for msg in thread_messages[1:]:
                        headers = {
                            h["name"]: h["value"]
                            for h in msg.get("payload", {}).get("headers", [])
                        }
                        replies.append(
                            {
                                "gmail_message_id": msg["id"],
                                "thread_id": tid,
                                "from": headers.get("From", ""),
                                "subject": headers.get("Subject", ""),
                                "date": headers.get("Date", ""),
                                "snippet": msg.get("snippet", ""),
                            }
                        )
            except Exception:
                # Skip threads that can't be fetched (deleted, etc.)
                continue

        return replies