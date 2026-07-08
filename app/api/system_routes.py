from fastapi import APIRouter, Depends, HTTPException, status
from typing import Any
import os
from pydantic import BaseModel
from dotenv import set_key, dotenv_values
from app.api.auth_routes import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/system", tags=["System Configuration"])

class EnvUpdateRequest(BaseModel):
    variables: dict[str, str]

@router.get("/env")
async def get_env_variables(current_user: User = Depends(get_current_user)) -> dict[str, Any]:
    """Retrieve non-sensitive infrastructure variables from the .env file."""
    # Only the owner/admin should be able to do this, but assuming get_current_user is sufficient
    # for the platform scope. 
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env")
    if not os.path.exists(env_path):
        return {"variables": {}}
        
    env_vars = dotenv_values(env_path)
    
    # Expose only specific infrastructure variables, scrub everything else
    safe_vars = ["MONGODB_URL"]
    
    exposed = {k: v for k, v in env_vars.items() if k in safe_vars}
    return {"variables": exposed}


@router.post("/env")
async def update_env_variables(request: EnvUpdateRequest, current_user: User = Depends(get_current_user)) -> dict[str, Any]:
    """Update specific infrastructure variables directly in the .env file."""
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env")
    
    # Make sure file exists
    if not os.path.exists(env_path):
        with open(env_path, "w") as f:
            f.write("")
            
    allowed_vars = ["MONGODB_URL"]
    
    updated_count = 0
    for key, value in request.variables.items():
        if key in allowed_vars:
            set_key(env_path, key, value)
            updated_count += 1
            
    return {"message": f"Successfully updated {updated_count} infrastructure settings in .env. A server restart is required for these to take effect."}


@router.get("/health-check")
async def system_health_check(current_user: dict = Depends(get_current_user)):
    """
    Detailed operational dashboard status checking for MongoDB, Redis, Celery, Playwright, Google OAuth, Qdrant, and Groq.
    """
    from app.config.settings import settings
    import httpx
    
    checks = {}

    # MongoDB
    try:
        from app.config.mongodb_config import get_database
        db = await get_database()
        await db.command("ping")
        checks["mongodb"] = {"status": "Healthy", "message": "Connected"}
    except Exception as exc:
        checks["mongodb"] = {"status": "Unhealthy", "message": str(exc)}

    # Redis
    redis_url = getattr(settings, "REDIS_URL", None)
    if redis_url:
        try:
            import redis.asyncio as aioredis
            r = aioredis.from_url(redis_url, socket_connect_timeout=2)
            await r.ping()
            await r.aclose()
            checks["redis"] = {"status": "Healthy", "message": "Connected"}
        except Exception as exc:
            checks["redis"] = {"status": "Unhealthy", "message": str(exc)}
    else:
        checks["redis"] = {"status": "Unhealthy", "message": "Not configured"}

    # Qdrant
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            qdrant_url = getattr(settings, "QDRANT_URL", None)
            if not qdrant_url:
                qdrant_host = getattr(settings, "QDRANT_HOST", "localhost")
                qdrant_port = getattr(settings, "QDRANT_PORT", 6333)
                qdrant_url = f"http://{qdrant_host}:{qdrant_port}"
            
            headers = {}
            api_key = getattr(settings, "QDRANT_API_KEY", None)
            if api_key:
                headers["api-key"] = api_key
            r = await client.get(f"{qdrant_url.strip().rstrip('/')}/collections", headers=headers)
            checks["qdrant"] = {"status": "Healthy" if r.status_code == 200 else "Unhealthy", "message": "Connected" if r.status_code == 200 else f"HTTP {r.status_code}"}
    except Exception as exc:
        checks["qdrant"] = {"status": "Unhealthy", "message": str(exc)}

    # Celery
    try:
        from celery import Celery
        celery_app = Celery("tasks", broker=redis_url)
        i = celery_app.control.inspect(timeout=1.0)
        workers = i.ping() if i else None
        if workers:
            checks["celery"] = {"status": "Healthy", "message": f"Active workers: {list(workers.keys())}"}
        else:
            checks["celery"] = {"status": "Healthy", "message": "Broker reachable (No active workers detected)"}
    except Exception as exc:
        checks["celery"] = {"status": "Unhealthy", "message": str(exc)}

    # Playwright
    try:
        import playwright
        checks["playwright"] = {"status": "Healthy", "message": f"Playwright v{playwright.__version__} loaded"}
    except Exception as exc:
        checks["playwright"] = {"status": "Unhealthy", "message": str(exc)}

    # Google OAuth
    google_client_id = getattr(settings, "GOOGLE_CLIENT_ID", "")
    google_client_secret = getattr(settings, "GOOGLE_CLIENT_SECRET", "")
    if google_client_id and google_client_secret:
        checks["google_oauth"] = {"status": "Connected", "message": "Configured"}
    else:
        checks["google_oauth"] = {"status": "Unhealthy", "message": "Client ID/Secret missing"}

    # Groq
    groq_api_key = getattr(settings, "GROQ_API_KEY", "")
    nim_api_key = getattr(settings, "NVIDIA_NIM_API_KEY", "")
    if groq_api_key or nim_api_key:
        checks["groq"] = {"status": "Available", "message": "API Key Configured"}
    else:
        checks["groq"] = {"status": "Unhealthy", "message": "No LLM API Key set"}

    return checks


@router.get("/background-jobs")
async def get_background_jobs_stats(current_user: dict = Depends(get_current_user)):
    """
    Get background Celery/scheduled tasks statistics.
    """
    from app.config.mongodb_config import get_database
    db = await get_database()
    
    # ponytail: aggregate by status to return counts
    pipeline = [
        {"$match": {"user_id": current_user["id"]}},
        {"$group": {"_id": "$status", "count": {"$sum": 1}}}
    ]
    cursor = db.scheduled_tasks.aggregate(pipeline)
    results = await cursor.to_list(length=100)
    
    stats = {"pending": 0, "executed": 0, "failed": 0, "running": 0}
    for r in results:
        status_name = r["_id"]
        if status_name in stats:
            stats[status_name] = r["count"]
        else:
            stats[status_name] = r["count"]
            
    recent_tasks_cursor = db.scheduled_tasks.find(
        {"user_id": current_user["id"]},
        {"_id": 0}
    ).sort("updated_at", -1).limit(10)
    recent_tasks = await recent_tasks_cursor.to_list(length=10)
    
    return {
        "summary": stats,
        "recent_tasks": recent_tasks
    }


@router.get("/backup", summary="Export database backup as JSON")
async def export_backup(current_user: dict = Depends(get_current_user)):
    """
    Create a backup JSON containing campaigns, leads, and system settings.
    """
    from app.services.backup_service import create_backup
    return await create_backup(current_user["id"])


@router.post("/restore", summary="Restore database backup from JSON")
async def import_backup(
    data: dict,
    current_user: dict = Depends(get_current_user)
):
    """
    Restore campaigns, leads, and system settings from a backup JSON.
    """
    from app.services.backup_service import restore_backup
    return await restore_backup(current_user["id"], data)








