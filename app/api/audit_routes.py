"""
Audit Trail API Routes.
"""

from fastapi import APIRouter, Depends, Query, Request

from app.auth.dependencies import get_current_user
from app.config.mongodb_config import get_database

router = APIRouter(prefix="/audit-logs", tags=["Audit Trail"])


@router.get("")
async def get_audit_logs(
    request: Request,
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user)
):
    """
    Retrieve audit logs.
    Non-admin users can only view their own logs.
    """
    db = await get_database()
    query = {}
    
    # ponytail: enforce strict tenant isolation - check user role
    role = current_user.get("role", "member")
    if role != "admin":
        query["user_id"] = current_user["id"]
        
    cursor = db.audit_logs.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit)
    logs = await cursor.to_list(length=limit)
    return logs
