"""
Gmail / Google OAuth2 configuration helpers.

Provides factory functions to build the OAuth2 flow, construct authenticated
Gmail API service objects, and refresh expired credentials.
"""

from __future__ import annotations

import logging
from typing import Any

from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build, Resource

from app.config.settings import settings

logger = logging.getLogger(__name__)

# ── Gmail API OAuth2 scopes ───────────────────────────────────────────────
GMAIL_SCOPES: list[str] = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
    "openid",
]


def create_oauth2_flow(
    *,
    state: str | None = None,
) -> Flow:
    """Create a Google OAuth2 ``Flow`` from application settings.

    Parameters
    ----------
    state:
        Optional opaque state string carried through the OAuth dance.

    Returns
    -------
    Flow
        A configured ``google_auth_oauthlib.flow.Flow`` instance.
    """
    client_config = {
        "web": {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.GOOGLE_REDIRECT_URI],
        }
    }

    flow = Flow.from_client_config(
        client_config,
        scopes=GMAIL_SCOPES,
        state=state,
    )
    flow.redirect_uri = settings.GOOGLE_REDIRECT_URI
    return flow


def build_gmail_service(credentials_dict: dict[str, Any]) -> Resource:
    """Construct an authenticated Gmail API service from stored credentials.

    Parameters
    ----------
    credentials_dict:
        A dict with keys: ``access_token``, ``refresh_token``, ``token_uri``,
        ``client_id``, ``client_secret``, and optionally ``scopes``.

    Returns
    -------
    Resource
        A ``googleapiclient`` service object for the Gmail API v1.
    """
    creds = Credentials(
        token=credentials_dict["access_token"],
        refresh_token=credentials_dict["refresh_token"],
        token_uri=credentials_dict.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=credentials_dict.get("client_id", settings.GOOGLE_CLIENT_ID),
        client_secret=credentials_dict.get("client_secret", settings.GOOGLE_CLIENT_SECRET),
        scopes=credentials_dict.get("scopes", GMAIL_SCOPES),
    )

    # Refresh if the token has already expired.
    if creds.expired and creds.refresh_token:
        creds.refresh(GoogleAuthRequest())
        logger.info("Gmail credentials refreshed automatically during service build.")

    service: Resource = build("gmail", "v1", credentials=creds, cache_discovery=False)
    return service


def refresh_credentials(credentials_dict: dict[str, Any]) -> dict[str, Any]:
    """Refresh an expired set of Google OAuth2 credentials.

    Parameters
    ----------
    credentials_dict:
        Same shape as accepted by :func:`build_gmail_service`.

    Returns
    -------
    dict
        Updated credentials dict with a fresh ``access_token`` (and possibly
        updated ``refresh_token``).

    Raises
    ------
    ValueError
        If no ``refresh_token`` is available.
    """
    refresh_token = credentials_dict.get("refresh_token")
    if not refresh_token:
        raise ValueError("Cannot refresh credentials without a refresh_token.")

    creds = Credentials(
        token=credentials_dict.get("access_token"),
        refresh_token=refresh_token,
        token_uri=credentials_dict.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=credentials_dict.get("client_id", settings.GOOGLE_CLIENT_ID),
        client_secret=credentials_dict.get("client_secret", settings.GOOGLE_CLIENT_SECRET),
        scopes=credentials_dict.get("scopes", GMAIL_SCOPES),
    )

    creds.refresh(GoogleAuthRequest())
    logger.info("Gmail credentials refreshed successfully.")

    return {
        "access_token": creds.token,
        "refresh_token": creds.refresh_token or refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes) if creds.scopes else GMAIL_SCOPES,
    }
