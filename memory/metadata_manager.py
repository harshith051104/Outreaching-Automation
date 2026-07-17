"""
Metadata manager — CRUD and tagging for memory metadata.

Operates on the MongoDB side of memory records (not vector payloads).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from memory.models import MemoryRecord

logger = logging.getLogger(__name__)


def build_metadata(
    collection: str,
    source: str = "",
    campaign_id: str = "",
    lead_id: str = "",
    user_id: str = "",
    tags: Optional[List[str]] = None,
    embedding_model: str = "",
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a standard metadata dict for a memory record."""
    now = datetime.now(timezone.utc).isoformat()
    meta: Dict[str, Any] = {
        "collection": collection,
        "source": source,
        "created_at": now,
        "updated_at": now,
        "embedding_model": embedding_model,
        "tags": tags or [],
    }
    if campaign_id:
        meta["campaign_id"] = campaign_id
    if lead_id:
        meta["lead_id"] = lead_id
    if user_id:
        meta["user_id"] = user_id
    if extra:
        meta.update(extra)
    return meta


def merge_metadata(existing: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    """Merge update fields into existing metadata, preserving immutables."""
    merged = existing.copy()
    now = datetime.now(timezone.utc).isoformat()
    merged["updated_at"] = now

    for key, value in updates.items():
        if key in ("created_at", "memory_id", "collection"):
            continue  # immutable
        if key == "tags" and isinstance(value, list):
            existing_tags = set(merged.get("tags", []))
            existing_tags.update(value)
            merged["tags"] = sorted(existing_tags)
        else:
            merged[key] = value
    return merged


def extract_filters(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Extract only filterable fields from metadata."""
    filterable = {"campaign_id", "lead_id", "user_id", "source", "collection", "tags", "status"}
    return {k: v for k, v in metadata.items() if k in filterable and v}


def add_tags(metadata: Dict[str, Any], tags: List[str]) -> Dict[str, Any]:
    """Add tags to metadata."""
    existing = set(metadata.get("tags", []))
    existing.update(tags)
    metadata["tags"] = sorted(existing)
    metadata["updated_at"] = datetime.now(timezone.utc).isoformat()
    return metadata


def remove_tags(metadata: Dict[str, Any], tags: List[str]) -> Dict[str, Any]:
    """Remove tags from metadata."""
    existing = set(metadata.get("tags", []))
    existing -= set(tags)
    metadata["tags"] = sorted(existing)
    metadata["updated_at"] = datetime.now(timezone.utc).isoformat()
    return metadata


def metadata_to_payload(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Convert metadata to a flat payload suitable for Qdrant."""
    payload = metadata.copy()
    # Qdrant payloads can't nest complex objects easily
    # Flatten tags to comma-separated string
    if "tags" in payload and isinstance(payload["tags"], list):
        payload["tags_csv"] = ",".join(payload["tags"])
    return payload
