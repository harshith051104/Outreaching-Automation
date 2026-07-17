"""
Memory lifecycle — create, update, archive, delete, expire, re-index.

Background maintenance for vector collections.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from memory.models import MemoryRecord, MemoryStatus
from memory.config import memory_config
from memory.vector_store import (
    upsert_point, delete_point, get_collection_info, ensure_collection,
)
from memory.version_manager import create_version, soft_delete, restore, prune_old_versions
from memory.metadata_manager import merge_metadata
from memory.embedding_engine import get_embedding_provider

logger = logging.getLogger(__name__)


def create_memory(
    collection: str,
    text: str,
    metadata: Optional[Dict[str, Any]] = None,
    doc_id: Optional[str] = None,
) -> MemoryRecord:
    """Create a new memory record with embedding."""
    provider = get_embedding_provider()
    emb = provider.embed_single(text)

    record = MemoryRecord(
        collection=collection,
        text=text,
        metadata=metadata or {},
        vector=emb.vector,
        embedding_model=emb.model,
        version=1,
    )
    if doc_id:
        record.memory_id = doc_id

    # Create version snapshot
    create_version(record)

    # Store in Qdrant
    payload = (metadata or {}).copy()
    payload["text"] = text
    payload["embedding_model"] = emb.model
    payload["version"] = 1

    upsert_point(collection, record.memory_id, emb.vector, payload)
    return record


def update_memory(
    collection: str,
    memory_id: str,
    text: Optional[str] = None,
    metadata_updates: Optional[Dict[str, Any]] = None,
) -> Optional[MemoryRecord]:
    """Update a memory (creates new version)."""
    from memory.version_manager import get_current_version

    current = get_current_version(memory_id)
    if current is None:
        logger.warning("Memory %s not found for update", memory_id)
        return None

    new_text = text if text is not None else current.text
    new_meta = merge_metadata(current.metadata, metadata_updates or {})

    provider = get_embedding_provider()
    emb = provider.embed_single(new_text)

    record = MemoryRecord(
        memory_id=memory_id,
        collection=collection,
        text=new_text,
        metadata=new_meta,
        vector=emb.vector,
        embedding_model=emb.model,
        version=current.version + 1,
    )

    create_version(record)

    payload = new_meta.copy()
    payload["text"] = new_text
    payload["embedding_model"] = emb.model
    payload["version"] = record.version

    upsert_point(collection, memory_id, emb.vector, payload)
    return record


def archive_memory(collection: str, memory_id: str) -> bool:
    """Archive a memory (soft delete with archived status)."""
    from memory.version_manager import get_current_version

    current = get_current_version(memory_id)
    if current is None:
        return False

    current.metadata["status"] = MemoryStatus.ARCHIVED.value
    current.metadata["archived_at"] = datetime.now(timezone.utc).isoformat()

    # Update Qdrant payload
    payload = current.metadata.copy()
    payload["text"] = current.text
    payload["status"] = MemoryStatus.ARCHIVED.value

    provider = get_embedding_provider()
    emb = provider.embed_single(current.text)
    upsert_point(collection, memory_id, emb.vector, payload)
    return True


def delete_memory(collection: str, memory_id: str) -> bool:
    """Hard delete a memory from Qdrant."""
    success = delete_point(collection, memory_id)
    if success:
        from memory.version_manager import clear_versions
        clear_versions(memory_id)
    return success


def expire_memories(collection: str) -> int:
    """Remove expired memories. Returns count removed."""
    from memory.version_manager import _version_store

    removed = 0
    now = datetime.now(timezone.utc)

    for memory_id, versions in list(_version_store.items()):
        current = None
        for v in reversed(versions):
            if v.is_current:
                current = v
                break

        if current and current.metadata.get("expires_at"):
            try:
                expires = datetime.fromisoformat(current.metadata["expires_at"])
                if now > expires:
                    delete_point(collection, memory_id)
                    _version_store.pop(memory_id, None)
                    removed += 1
            except Exception:
                pass

    return removed


def reindex_collection(collection: str) -> Dict[str, Any]:
    """Re-index all memories in a collection (re-generate embeddings)."""
    from memory.version_manager import _version_store

    reindexed = 0
    provider = get_embedding_provider()

    for memory_id, versions in _version_store.items():
        current = None
        for v in reversed(versions):
            if v.is_current:
                current = v
                break

        if current and current.metadata.get("collection") == collection:
            emb = provider.embed_single(current.text)
            payload = current.metadata.copy()
            payload["text"] = current.text
            upsert_point(collection, memory_id, emb.vector, payload)
            reindexed += 1

    return {"collection": collection, "reindexed": reindexed}


def get_memory_stats(collection: str) -> Dict[str, Any]:
    """Get statistics for a collection."""
    info = get_collection_info(collection)
    return {
        "collection": collection,
        "exists": info.get("exists", False),
        "points_count": info.get("points_count", 0),
        "status": info.get("status", "unknown"),
    }
