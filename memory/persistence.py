"""
MongoDB persistence for memory metadata.

Stores memory records, version history, and metadata on MongoDB.
Qdrant stores vectors; MongoDB stores everything else.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from memory.models import MemoryRecord, MemoryStatus, VersionRecord

logger = logging.getLogger(__name__)


async def _get_db():
    from app.config.mongodb_config import get_database
    return await get_database()


async def save_memory_record(record: MemoryRecord) -> bool:
    """Save or update a memory record in MongoDB."""
    try:
        db = await _get_db()
        doc = record.to_doc()
        doc["_id"] = record.memory_id
        await db.memory_records.update_one(
            {"_id": record.memory_id},
            {"$set": doc},
            upsert=True,
        )
        return True
    except Exception as exc:
        logger.error("Failed to save memory record %s: %s", record.memory_id, exc)
        return False


async def get_memory_record(memory_id: str) -> Optional[MemoryRecord]:
    """Retrieve a memory record from MongoDB."""
    try:
        db = await _get_db()
        doc = await db.memory_records.find_one({"_id": memory_id})
        if doc:
            doc["memory_id"] = doc.pop("_id", memory_id)
            return MemoryRecord.from_doc(doc)
        return None
    except Exception as exc:
        logger.error("Failed to get memory record %s: %s", memory_id, exc)
        return None


async def list_memory_records(
    collection: str = "",
    user_id: str = "",
    campaign_id: str = "",
    lead_id: str = "",
    status: Optional[str] = None,
    limit: int = 100,
) -> List[MemoryRecord]:
    """List memory records with optional filters."""
    try:
        db = await _get_db()
        query: Dict[str, Any] = {}
        if collection:
            query["collection"] = collection
        if user_id:
            query["user_id"] = user_id
        if campaign_id:
            query["campaign_id"] = campaign_id
        if lead_id:
            query["lead_id"] = lead_id
        if status:
            query["status"] = status

        cursor = db.memory_records.find(query).limit(limit)
        records = []
        async for doc in cursor:
            doc["memory_id"] = doc.pop("_id", "")
            records.append(MemoryRecord.from_doc(doc))
        return records
    except Exception as exc:
        logger.error("Failed to list memory records: %s", exc)
        return []


async def save_version_record(vr: VersionRecord) -> bool:
    """Save a version record."""
    try:
        db = await _get_db()
        doc = vr.to_doc()
        doc["_id"] = f"{vr.memory_id}_v{vr.version}"
        await db.memory_versions.update_one(
            {"_id": doc["_id"]},
            {"$set": doc},
            upsert=True,
        )
        return True
    except Exception as exc:
        logger.error("Failed to save version record: %s", exc)
        return False


async def get_version_history(memory_id: str) -> List[VersionRecord]:
    """Get all versions for a memory from MongoDB."""
    try:
        db = await _get_db()
        cursor = db.memory_versions.find(
            {"memory_id": memory_id}
        ).sort("version", -1)
        versions = []
        async for doc in cursor:
            doc.pop("_id", None)
            versions.append(VersionRecord(
                memory_id=doc.get("memory_id", ""),
                version=doc.get("version", 1),
                text=doc.get("text", ""),
                metadata=doc.get("metadata", {}),
                created_at=doc.get("created_at", ""),
                is_current=doc.get("is_current", False),
            ))
        return versions
    except Exception as exc:
        logger.error("Failed to get version history for %s: %s", memory_id, exc)
        return []


async def delete_memory_record(memory_id: str) -> bool:
    """Delete a memory record from MongoDB."""
    try:
        db = await _get_db()
        await db.memory_records.delete_one({"_id": memory_id})
        await db.memory_versions.delete_many({"memory_id": memory_id})
        return True
    except Exception as exc:
        logger.error("Failed to delete memory record %s: %s", memory_id, exc)
        return False


async def count_memory_records(collection: str = "") -> int:
    """Count memory records."""
    try:
        db = await _get_db()
        query = {"collection": collection} if collection else {}
        return await db.memory_records.count_documents(query)
    except Exception:
        return 0
