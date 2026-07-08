"""
Audit Trail Logging Service.
ponytail: Simple MongoDB logger.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from app.config.mongodb_config import get_database
from app.utils.id_generator import generate_id

logger = logging.getLogger(__name__)


async def log_audit_event(
    user_id: str,
    action: str,
    resource: str,
    result: str,
    client_ip: str = "unknown",
    metadata: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Log an audit event to the database.
    """
    try:
        db = await get_database()
        event_doc = {
            "id": generate_id(),
            "user_id": user_id,
            "action": action,
            "resource": resource,
            "result": result,
            "client_ip": client_ip,
            "metadata": metadata or {},
            "created_at": datetime.now(timezone.utc),
        }
        await db.audit_logs.insert_one(event_doc)
        logger.info(f"AuditLog: {action} on {resource} by {user_id} - {result}")
        event_doc.pop("_id", None)
        return event_doc
    except Exception as exc:
        logger.error(f"Failed to write audit log: {exc}")
        return {}
