"""
Integrations API Routes — /api/integrations

Provides endpoints for managing per-user API credentials and testing
connectivity to all external providers. All credentials are stored
encrypted via the integrations_service.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.services import integrations_service

router = APIRouter(prefix="/integrations", tags=["Integrations"])


# ─────────────────────────────────────────────────────────────────────────────
# Request / Response schemas
# ─────────────────────────────────────────────────────────────────────────────

class AIConfigSchema(BaseModel):
    research_model: str = "llama-3.3-70b-versatile"
    email_model: str = "llama-3.3-70b-versatile"
    classifier_model: str = "llama-3.3-70b-versatile"
    router_mode: str = "dynamic_routing"
    similarity_threshold: float = 0.7
    recency_weight: float = 0.3
    llm_api_key: str = ""


class SaveIntegrationRequest(BaseModel):
    credentials: dict[str, Any]
    """Plain-text key/value pairs, e.g. {"api_key": "sk-..."}"""


class IntegrationStatusResponse(BaseModel):
    provider: str
    label: str
    connected: bool
    last_tested_at: Any = None
    last_test_ok: bool | None = None
    last_error: str = ""
    updated_at: Any = None


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────


@router.get("", response_model=list[IntegrationStatusResponse])
async def list_integrations(current_user: dict = Depends(get_current_user)):
    """
    List all provider integration statuses for the current user.
    Never returns decrypted credentials.
    """
    return await integrations_service.list_integrations(current_user["id"])


@router.get("/health/all")
async def get_health(current_user: dict = Depends(get_current_user)):
    """
    Return health status for all infrastructure components:
    MongoDB, Qdrant, Redis.
    """
    return await integrations_service.get_health_status()


@router.put("/{provider}", status_code=status.HTTP_200_OK)
async def save_integration(
    provider: str,
    body: SaveIntegrationRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Save (or update) encrypted credentials for a provider.

    Body: ``{"credentials": {"api_key": "sk-..."}}``
    """
    if not body.credentials:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="credentials must be a non-empty dict.",
        )
    await integrations_service.save_integration(
        user_id=current_user["id"],
        provider=provider,
        credentials=body.credentials,
    )
    return {"message": f"{provider} credentials saved successfully."}


@router.delete("/{provider}", status_code=status.HTTP_200_OK)
async def delete_integration(
    provider: str,
    current_user: dict = Depends(get_current_user),
):
    """Remove a provider's credentials for the current user."""
    deleted = await integrations_service.delete_integration(
        user_id=current_user["id"],
        provider=provider,
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No credentials found for provider '{provider}'.",
        )
    return {"message": f"{provider} credentials removed."}


@router.post("/{provider}/test")
async def test_integration(
    provider: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Run a live connectivity test for the given provider.

    Returns ``{"ok": true/false, "message": "..."}``
    """
    result = await integrations_service.test_integration(
        user_id=current_user["id"],
        provider=provider,
    )
    return result


@router.get("/ai-config", response_model=AIConfigSchema)
async def get_ai_config(current_user: dict = Depends(get_current_user)):
    from app.config.mongodb_config import get_database
    db = await get_database()
    config = await db.system_settings.find_one({"user_id": current_user["id"], "type": "ai_config"})
    if config:
        config.pop("_id", None)
        # mask the api key for security
        api_key = config.get("llm_api_key", "")
        if api_key:
            config["llm_api_key"] = "*" * (len(api_key) - 4) + api_key[-4:] if len(api_key) > 4 else "***"
        return AIConfigSchema(**config)
    return AIConfigSchema()


@router.post("/ai-config")
async def save_ai_config(body: AIConfigSchema, current_user: dict = Depends(get_current_user)):
    from app.config.mongodb_config import get_database
    db = await get_database()
    
    update_data = body.dict()
    # Need to keep the old api key if the new one is masked
    if update_data.get("llm_api_key") and update_data["llm_api_key"].startswith("*"):
        existing = await db.system_settings.find_one({"user_id": current_user["id"], "type": "ai_config"})
        if existing and "llm_api_key" in existing:
            update_data["llm_api_key"] = existing["llm_api_key"]

    await db.system_settings.update_one(
        {"user_id": current_user["id"], "type": "ai_config"},
        {"$set": update_data},
        upsert=True
    )
    return {"message": "AI configuration saved successfully."}
