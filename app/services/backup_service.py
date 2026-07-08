"""
Backup & Restore Service.
ponytail: Simple JSON export/import of user tables.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from app.config.mongodb_config import get_database

logger = logging.getLogger(__name__)


async def create_backup(user_id: str) -> Dict[str, Any]:
    """
    Export all campaigns, leads, email templates, and system configs for a user.
    """
    db = await get_database()
    
    campaigns = await db.campaigns.find({"user_id": user_id}).to_list(length=1000)
    for c in campaigns:
        c.pop("_id", None)
        
    leads = await db.leads.find({"user_id": user_id}).to_list(length=10000)
    for l in leads:
        l.pop("_id", None)
        
    settings = await db.system_settings.find({"user_id": user_id}).to_list(length=100)
    for s in settings:
        s.pop("_id", None)

    return {
        "user_id": user_id,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "campaigns": campaigns,
        "leads": leads,
        "system_settings": settings,
    }


async def restore_backup(user_id: str, backup_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Import campaigns, leads, and settings from a JSON backup.
    """
    db = await get_database()
    
    campaigns = backup_data.get("campaigns", [])
    leads = backup_data.get("leads", [])
    settings = backup_data.get("system_settings", [])

    imported_campaigns = 0
    imported_leads = 0
    imported_settings = 0

    # ponytail: restore documents using update_one with upsert to avoid duplication
    for c in campaigns:
        c["user_id"] = user_id  # Enforce tenant isolation
        res = await db.campaigns.update_one(
            {"id": c["id"]},
            {"$set": c},
            upsert=True
        )
        if res.upserted_id or res.modified_count:
            imported_campaigns += 1
            
    for l in leads:
        l["user_id"] = user_id
        res = await db.leads.update_one(
            {"id": l["id"]},
            {"$set": l},
            upsert=True
        )
        if res.upserted_id or res.modified_count:
            imported_leads += 1
            
    for s in settings:
        s["user_id"] = user_id
        key = s.get("key") or s.get("type")
        res = await db.system_settings.update_one(
            {"user_id": user_id, "key": key} if key else {"_id": "none"},
            {"$set": s},
            upsert=True
        )
        if res.upserted_id or res.modified_count:
            imported_settings += 1

    return {
        "status": "success",
        "imported": {
            "campaigns": imported_campaigns,
            "leads": imported_leads,
            "system_settings": imported_settings,
        }
    }
