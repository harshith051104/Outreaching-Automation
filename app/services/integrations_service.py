"""
Integrations Service — manages per-user encrypted API credentials.

This service is the single source of truth for all third-party API keys,
OAuth tokens, and session credentials stored per user.  All data stored
via this service is encrypted at rest using :mod:`app.utils.security`.

Providers:
    groq           — Groq AI API key
    tavily         — Tavily web-search API key
    firecrawl      — Firecrawl scraping API key
    apollo         — Apollo.io API key
    hunter         — Hunter.io API key
    linkedin_session — Playwright cookie JSON string
    google_sheets  — spreadsheet_id + service_account_json
    gmail_oauth    — managed by OAuth flow (read-only here)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from app.config.mongodb_config import get_database
from app.models.user_integration import PROVIDER_LABELS, UserIntegration
from app.utils.security import decrypt_dict, encrypt_dict

logger = logging.getLogger(__name__)

_COLLECTION = "user_integrations"


# ─────────────────────────────────────────────────────────────────────────────
# Core CRUD helpers
# ─────────────────────────────────────────────────────────────────────────────


async def save_integration(user_id: str, provider: str, credentials: dict[str, Any]) -> None:
    """
    Encrypt and store (or update) a provider's credentials for ``user_id``.

    ``credentials`` is a plain-text dict, e.g. ``{"api_key": "sk-..."}``.
    All string values are encrypted before storage.
    """
    db = await get_database()
    encrypted = encrypt_dict(credentials)
    now = datetime.now(timezone.utc)

    await db[_COLLECTION].update_one(
        {"user_id": user_id, "provider": provider},
        {
            "$set": {
                "encrypted_data": encrypted,
                "is_active": True,
                "last_error": "",
                "updated_at": now,
            },
            "$setOnInsert": {
                "id": UserIntegration(user_id=user_id, provider=provider).id,
                "created_at": now,
            },
        },
        upsert=True,
    )
    logger.info("Integration saved: user=%s provider=%s", user_id, provider)


async def get_integration(user_id: str, provider: str) -> dict[str, Any] | None:
    """
    Retrieve and decrypt credentials for a provider.

    Returns the plain-text credential dict, or ``None`` if not configured.
    """
    db = await get_database()
    doc = await db[_COLLECTION].find_one({"user_id": user_id, "provider": provider})
    if not doc:
        return None
    encrypted = doc.get("encrypted_data", {})
    try:
        return decrypt_dict(encrypted)
    except Exception as exc:
        logger.error("Failed to decrypt integration for user=%s provider=%s: %s", user_id, provider, exc)
        return None


async def delete_integration(user_id: str, provider: str) -> bool:
    """Remove a provider's credentials for ``user_id``."""
    db = await get_database()
    result = await db[_COLLECTION].delete_one({"user_id": user_id, "provider": provider})
    return result.deleted_count > 0


async def list_integrations(user_id: str) -> list[dict[str, Any]]:
    """
    Return a status summary for all known providers for ``user_id``.

    Safe to send to the frontend — never includes decrypted credentials.
    """
    db = await get_database()
    docs = await db[_COLLECTION].find({"user_id": user_id}).to_list(length=50)

    # Build a lookup by provider
    configured: dict[str, dict] = {d["provider"]: d for d in docs}

    result = []
    for provider, label in PROVIDER_LABELS.items():
        doc = configured.get(provider)
        if doc:
            result.append({
                "provider": provider,
                "label": label,
                "connected": True,
                "last_tested_at": doc.get("last_tested_at"),
                "last_test_ok": doc.get("last_test_ok"),
                "last_error": doc.get("last_error", ""),
                "updated_at": doc.get("updated_at"),
            })
        else:
            result.append({
                "provider": provider,
                "label": label,
                "connected": False,
                "last_tested_at": None,
                "last_test_ok": None,
                "last_error": "",
                "updated_at": None,
            })
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Key resolver — used by other services to get the API key with .env fallback
# ─────────────────────────────────────────────────────────────────────────────


async def get_api_key(user_id: str, provider: str, env_fallback: str | None = None) -> str | None:
    """
    Retrieve the API key for ``provider`` for ``user_id``.

    Falls back to ``env_fallback`` (typically from ``settings``) if the user
    has no personal key configured.
    """
    creds = await get_integration(user_id, provider)
    if creds and creds.get("api_key"):
        return creds["api_key"]
    return env_fallback


def get_api_key_sync(user_id: str, provider: str, env_fallback: str | None = None) -> str | None:
    """
    Synchronous version of get_api_key using pymongo.
    Prevents asyncio event loop conflicts when called from sync contexts.
    """
    from pymongo import MongoClient
    from app.config.settings import settings
    try:
        client = MongoClient(settings.MONGODB_URL, serverSelectionTimeoutMS=2000)
        db = client[settings.MONGODB_DB_NAME]
        doc = db[_COLLECTION].find_one({"user_id": user_id, "provider": provider})
        if doc and "encrypted_data" in doc:
            creds = decrypt_dict(doc["encrypted_data"])
            if creds and creds.get("api_key"):
                return creds["api_key"]
    except Exception as exc:
        logger.error("Failed sync decrypt for user=%s provider=%s: %s", user_id, provider, exc)
    return env_fallback


# ─────────────────────────────────────────────────────────────────────────────
# Test connection implementations
# ─────────────────────────────────────────────────────────────────────────────


async def test_integration(user_id: str, provider: str) -> dict[str, Any]:
    """
    Attempt a live connection test for ``provider`` using the stored credentials.

    Returns ``{"ok": bool, "message": str}``.
    """
    creds = await get_integration(user_id, provider)
    if not creds:
        return {"ok": False, "message": "No credentials configured for this provider."}

    try:
        result = await _run_test(provider, creds)
    except Exception as exc:
        result = {"ok": False, "message": str(exc)}

    # Persist the test result
    db = await get_database()
    await db[_COLLECTION].update_one(
        {"user_id": user_id, "provider": provider},
        {
            "$set": {
                "last_tested_at": datetime.now(timezone.utc),
                "last_test_ok": result["ok"],
                "last_error": "" if result["ok"] else result.get("message", ""),
                "updated_at": datetime.now(timezone.utc),
            }
        },
    )
    return result


async def _run_test(provider: str, creds: dict) -> dict[str, Any]:
    """Dispatch to provider-specific test logic."""
    if provider == "groq":
        return await _test_groq(creds)
    elif provider == "nvidia":
        return await _test_nvidia(creds)
    elif provider == "xiaomi":
        return await _test_xiaomi(creds)
    elif provider == "tavily":
        return await _test_tavily(creds)
    elif provider == "firecrawl":
        return await _test_firecrawl(creds)
    elif provider == "apollo":
        return await _test_apollo(creds)
    elif provider == "hunter":
        return await _test_hunter(creds)
    elif provider == "linkedin_session":
        return await _test_linkedin(creds)
    elif provider == "google_sheets":
        return await _test_google_sheets(creds)
    else:
        return {"ok": False, "message": f"No test implementation for provider '{provider}'."}


async def _test_nvidia(creds: dict) -> dict:
    api_key = creds.get("api_key", "")
    if not api_key:
        return {"ok": False, "message": "API key is empty."}
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            r = await client.get(
                "https://integrate.api.nvidia.com/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            if r.status_code == 200:
                return {"ok": True, "message": "Nvidia NIM connection successful."}
            return {"ok": False, "message": f"Nvidia NIM returned {r.status_code}: {r.text[:100]}"}
        except Exception as e:
            return {"ok": False, "message": f"Nvidia NIM connection failed: {e}"}


async def _test_xiaomi(creds: dict) -> dict:
    api_key = creds.get("api_key", "")
    if not api_key:
        return {"ok": False, "message": "API key is empty."}
    return {"ok": True, "message": "Xiaomi API key saved."}


async def _test_groq(creds: dict) -> dict:
    api_key = creds.get("api_key", "")
    if not api_key:
        return {"ok": False, "message": "API key is empty."}
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            "https://api.groq.com/openai/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
        )
    if r.status_code == 200:
        return {"ok": True, "message": "Groq connection successful."}
    return {"ok": False, "message": f"Groq returned {r.status_code}: {r.text[:200]}"}


async def _test_tavily(creds: dict) -> dict:
    api_key = creds.get("api_key", "")
    if not api_key:
        return {"ok": False, "message": "API key is empty."}
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(
            "https://api.tavily.com/search",
            json={"query": "test", "max_results": 1},
            headers={"Authorization": f"Bearer {api_key}"},
        )
    if r.status_code in (200, 201):
        return {"ok": True, "message": "Tavily connection successful."}
    return {"ok": False, "message": f"Tavily returned {r.status_code}: {r.text[:200]}"}


async def _test_firecrawl(creds: dict) -> dict:
    api_key = creds.get("api_key", "")
    if not api_key:
        return {"ok": False, "message": "API key is empty."}
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            "https://api.firecrawl.dev/v0/crawl/status/test",
            headers={"Authorization": f"Bearer {api_key}"},
        )
    # 404 means the API is reachable but no such job (expected for test ID)
    if r.status_code in (200, 404):
        return {"ok": True, "message": "Firecrawl API key is valid."}
    return {"ok": False, "message": f"Firecrawl returned {r.status_code}: {r.text[:200]}"}


async def _test_apollo(creds: dict) -> dict:
    api_key = creds.get("api_key", "")
    if not api_key:
        return {"ok": False, "message": "API key is empty."}
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(
            "https://api.apollo.io/api/v1/auth/health",
            headers={"Content-Type": "application/json", "Cache-Control": "no-cache"},
            json={"api_key": api_key},
        )
    if r.status_code == 200:
        return {"ok": True, "message": "Apollo connection successful."}
    return {"ok": False, "message": f"Apollo returned {r.status_code}: {r.text[:200]}"}


async def _test_hunter(creds: dict) -> dict:
    api_key = creds.get("api_key", "")
    if not api_key:
        return {"ok": False, "message": "API key is empty."}
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            f"https://api.hunter.io/v2/account?api_key={api_key}",
        )
    if r.status_code == 200:
        return {"ok": True, "message": "Hunter.io connection successful."}
    return {"ok": False, "message": f"Hunter returned {r.status_code}: {r.text[:200]}"}


async def _test_linkedin(creds: dict) -> dict:
    cookie = creds.get("cookie", "")
    if not cookie:
        return {"ok": False, "message": "LinkedIn session cookie is empty."}
    # Just validate JSON parseability; actual Playwright test would require subprocess
    try:
        parsed = json.loads(cookie) if isinstance(cookie, str) else cookie
        if isinstance(parsed, list) and len(parsed) > 0:
            return {"ok": True, "message": f"LinkedIn session has {len(parsed)} cookies stored."}
        return {"ok": False, "message": "Cookie JSON is empty or malformed."}
    except json.JSONDecodeError:
        return {"ok": False, "message": "Cookie value is not valid JSON."}


async def _test_google_sheets(creds: dict) -> dict:
    spreadsheet_id = creds.get("spreadsheet_id", "")
    service_account_json = creds.get("service_account_json", "")
    if not spreadsheet_id:
        return {"ok": False, "message": "Spreadsheet ID is not configured."}
    if not service_account_json:
        return {"ok": False, "message": "Service Account JSON is not configured."}
    try:
        json.loads(service_account_json)
    except json.JSONDecodeError:
        return {"ok": False, "message": "Service Account JSON is not valid JSON."}
    return {"ok": True, "message": "Google Sheets credentials are configured (live test runs on first sync)."}


# ─────────────────────────────────────────────────────────────────────────────
# Infrastructure health check
# ─────────────────────────────────────────────────────────────────────────────


async def get_health_status() -> dict[str, Any]:
    """
    Check health of all platform infrastructure components.

    Returns a dict safe to expose to the frontend.
    """
    from app.config.settings import settings

    checks: dict[str, dict] = {}

    # MongoDB
    try:
        db = await get_database()
        await db.command("ping")
        checks["mongodb"] = {"ok": True, "message": "Connected"}
    except Exception as exc:
        checks["mongodb"] = {"ok": False, "message": str(exc)}

    # Qdrant
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            qdrant_url = getattr(settings, "QDRANT_URL", None)
            if not qdrant_url:
                qdrant_host = getattr(settings, "QDRANT_HOST", "localhost")
                qdrant_port = getattr(settings, "QDRANT_PORT", 6333)
                qdrant_url = f"http://{qdrant_host}:{qdrant_port}"
            
            headers = {}
            api_key = getattr(settings, "QDRANT_API_KEY", None)
            if api_key:
                headers["api-key"] = api_key

            clean_url = qdrant_url.strip().rstrip('/')
            r = await client.get(f"{clean_url}/collections", headers=headers)
            checks["qdrant"] = {"ok": r.status_code == 200, "message": "Connected" if r.status_code == 200 else f"HTTP {r.status_code}"}
    except Exception as exc:
        checks["qdrant"] = {"ok": False, "message": str(exc)}

    # Redis (check if REDIS_URL is configured)
    redis_url = getattr(settings, "REDIS_URL", None) or getattr(settings, "CELERY_BROKER_URL", None)
    if redis_url:
        try:
            import redis.asyncio as aioredis
            r = aioredis.from_url(redis_url, socket_connect_timeout=3)
            await r.ping()
            await r.aclose()
            checks["redis"] = {"ok": True, "message": "Connected"}
        except Exception as exc:
            checks["redis"] = {"ok": False, "message": str(exc)}
    else:
        checks["redis"] = {"ok": None, "message": "Not configured"}

    return checks
