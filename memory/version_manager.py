"""
Version manager — version history, soft delete, rollback, re-index.

Every memory update creates a new version. Never overwrite without tracking.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from memory.models import MemoryRecord, MemoryStatus, VersionRecord
from memory.config import memory_config

logger = logging.getLogger(__name__)

# In-memory version store (production would use MongoDB)
_version_store: Dict[str, List[VersionRecord]] = {}


def create_version(record: MemoryRecord) -> VersionRecord:
    """Create a version snapshot of a memory record."""
    vr = VersionRecord(
        memory_id=record.memory_id,
        version=record.version,
        text=record.text,
        metadata=record.metadata.copy(),
        is_current=True,
    )
    if record.memory_id not in _version_store:
        _version_store[record.memory_id] = []

    # Mark previous versions as not current
    for prev in _version_store[record.memory_id]:
        prev.is_current = False

    _version_store[record.memory_id].append(vr)
    return vr


def get_current_version(memory_id: str) -> Optional[VersionRecord]:
    """Get the current version of a memory."""
    versions = _version_store.get(memory_id, [])
    for v in reversed(versions):
        if v.is_current:
            return v
    return versions[-1] if versions else None


def get_version_history(memory_id: str) -> List[VersionRecord]:
    """Get all versions of a memory."""
    return list(_version_store.get(memory_id, []))


def rollback(memory_id: str, target_version: int) -> Optional[VersionRecord]:
    """Rollback a memory to a specific version."""
    versions = _version_store.get(memory_id, [])
    target = None
    for v in versions:
        if v.version == target_version:
            target = v
            break

    if target is None:
        logger.warning("Version %d not found for %s", target_version, memory_id)
        return None

    # Mark all as not current, set target as current
    for v in versions:
        v.is_current = False
    target.is_current = True

    logger.info("Rolled back %s to version %d", memory_id, target_version)
    return target


def soft_delete(memory_id: str) -> bool:
    """Mark a memory as deleted without removing it."""
    versions = _version_store.get(memory_id, [])
    if not versions:
        return False

    current = get_current_version(memory_id)
    if current:
        current.metadata["status"] = MemoryStatus.DELETED.value
        current.metadata["deleted_at"] = datetime.now(timezone.utc).isoformat()
    return True


def restore(memory_id: str) -> bool:
    """Restore a soft-deleted memory."""
    current = get_current_version(memory_id)
    if not current:
        return False

    status = current.metadata.get("status")
    if status == MemoryStatus.DELETED.value:
        current.metadata["status"] = MemoryStatus.ACTIVE.value
        current.metadata.pop("deleted_at", None)
        return True
    return False


def prune_old_versions(memory_id: str) -> int:
    """Remove old versions beyond the configured max. Returns count removed."""
    max_versions = memory_config.lifecycle.max_versions_per_memory
    versions = _version_store.get(memory_id, [])
    if len(versions) <= max_versions:
        return 0

    # Keep the most recent versions + current
    current = get_current_version(memory_id)
    sorted_versions = sorted(versions, key=lambda v: v.version, reverse=True)
    to_keep = set()
    for v in sorted_versions[:max_versions]:
        to_keep.add(id(v))
    if current:
        to_keep.add(id(current))

    before = len(versions)
    _version_store[memory_id] = [v for v in versions if id(v) in to_keep]
    return before - len(_version_store[memory_id])


def clear_versions(memory_id: str) -> None:
    """Clear all versions for a memory."""
    _version_store.pop(memory_id, None)


def _reset_store() -> None:
    """Reset version store (for testing)."""
    global _version_store
    _version_store = {}
