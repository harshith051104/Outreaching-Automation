"""
Vector store — Qdrant collection management, CRUD, upsert, versioning.

Manages all vector operations against Qdrant. Each module has a single
responsibility: this module owns vector-level I/O only.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from memory.models import CollectionConfig, MemoryRecord, MemoryStatus
from memory.config import memory_config, COLLECTION_MAP

logger = logging.getLogger(__name__)

HAS_QDRANT = True

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models as qdrant_models
    from qdrant_client.http.exceptions import UnexpectedResponse
except ImportError:
    HAS_QDRANT = False

# Module-level client cache
_client: Optional[Any] = None


def get_client() -> Any:
    """Return cached Qdrant client (mirrors app.config.qdrant_config)."""
    global _client
    if _client is not None:
        return _client

    if not HAS_QDRANT:
        return None

    try:
        from app.config.qdrant_config import get_qdrant_client
        _client = get_qdrant_client()
        return _client
    except Exception:
        logger.warning("Qdrant client unavailable; vector operations will be no-ops.")
        return None


def ensure_collection(config: CollectionConfig) -> bool:
    """Create a collection if it doesn't exist. Returns True if created."""
    client = get_client()
    if client is None:
        return False

    try:
        existing = {c.name for c in client.get_collections().collections}
        if config.name in existing:
            return False

        distance_map = {
            "COSINE": qdrant_models.Distance.COSINE,
            "EUCLID": qdrant_models.Distance.EUCLID,
            "DOT": qdrant_models.Distance.DOT,
            "MANHATTAN": qdrant_models.Distance.MANHATTAN,
        }
        distance = distance_map.get(config.distance.upper(), qdrant_models.Distance.COSINE)

        client.create_collection(
            collection_name=config.name,
            vectors_config=qdrant_models.VectorParams(
                size=config.vector_size,
                distance=distance,
            ),
        )
        logger.info("Created Qdrant collection: %s (dim=%d)", config.name, config.vector_size)
        return True
    except Exception as exc:
        logger.error("Failed to create collection %s: %s", config.name, exc)
        return False


def ensure_all_collections() -> None:
    """Create all configured collections if they don't exist."""
    for config in memory_config.collections:
        ensure_collection(config)


def upsert_point(
    collection_name: str,
    doc_id: str,
    vector: List[float],
    payload: Dict[str, Any],
) -> bool:
    """Upsert a single point into Qdrant."""
    client = get_client()
    if client is None:
        return False

    try:
        from qdrant_client.http.models import PointStruct
        point = PointStruct(id=doc_id, vector=vector, payload=payload)
        client.upsert(collection_name=collection_name, points=[point])
        return True
    except Exception as exc:
        logger.error("Upsert failed for %s/%s: %s", collection_name, doc_id, exc)
        return False


def upsert_batch(
    collection_name: str,
    points: List[Dict[str, Any]],
    batch_size: int = 100,
) -> int:
    """Upsert a batch of points. Returns count of successfully upserted."""
    client = get_client()
    if client is None or not points:
        return 0

    try:
        from qdrant_client.http.models import PointStruct
        count = 0
        for i in range(0, len(points), batch_size):
            batch = points[i : i + batch_size]
            structs = [
                PointStruct(id=p["id"], vector=p["vector"], payload=p.get("payload", {}))
                for p in batch
            ]
            client.upsert(collection_name=collection_name, points=structs)
            count += len(structs)
        return count
    except Exception as exc:
        logger.error("Batch upsert failed for %s: %s", collection_name, exc)
        return 0


def search(
    collection_name: str,
    query_vector: List[float],
    limit: int = 3,
    score_threshold: Optional[float] = None,
    query_filter: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """Raw vector search. Returns list of {id, text, score, metadata}."""
    client = get_client()
    if client is None:
        return []

    try:
        kwargs: Dict[str, Any] = {
            "collection_name": collection_name,
            "query": query_vector,
            "limit": limit,
        }
        if score_threshold is not None:
            kwargs["score_threshold"] = score_threshold
        if query_filter is not None:
            kwargs["query_filter"] = query_filter

        if hasattr(client, "query_points"):
            res = client.query_points(**kwargs)
            hits = res.points
        elif hasattr(client, "search"):
            kwargs["query_vector"] = kwargs.pop("query")
            hits = client.search(**kwargs)
        else:
            return []

        results = []
        for hit in hits:
            hit_id = getattr(hit, "id", None)
            score = getattr(hit, "score", 0.0)
            payload = getattr(hit, "payload", {}) or {}
            text_content = payload.get("text", "")
            results.append({
                "id": hit_id,
                "text": text_content,
                "score": score,
                "metadata": payload,
            })
        return results
    except Exception as exc:
        logger.error("Search failed for %s: %s", collection_name, exc)
        return []


def delete_point(collection_name: str, doc_id: str) -> bool:
    """Delete a single point from Qdrant."""
    client = get_client()
    if client is None:
        return False

    try:
        client.delete(
            collection_name=collection_name,
            points_selector=qdrant_models.PointIdsList(points=[doc_id]),
        )
        return True
    except Exception as exc:
        logger.error("Delete failed for %s/%s: %s", collection_name, doc_id, exc)
        return False


def delete_batch(collection_name: str, doc_ids: List[str]) -> bool:
    """Delete multiple points from Qdrant."""
    client = get_client()
    if client is None or not doc_ids:
        return False

    try:
        client.delete(
            collection_name=collection_name,
            points_selector=qdrant_models.PointIdsList(points=doc_ids),
        )
        return True
    except Exception as exc:
        logger.error("Batch delete failed for %s: %s", collection_name, exc)
        return False


def get_collection_info(collection_name: str) -> Dict[str, Any]:
    """Get collection metadata (point count, config)."""
    client = get_client()
    if client is None:
        return {"exists": False, "points_count": 0}

    try:
        info = client.get_collection(collection_name)
        return {
            "exists": True,
            "points_count": info.points_count or 0,
            "vectors_count": info.vectors_count or 0,
            "status": str(info.status) if hasattr(info, "status") else "unknown",
            "config": {
                "vector_size": info.config.params.vectors.size if hasattr(info, "config") else 384,
                "distance": str(info.config.params.vectors.distance) if hasattr(info, "config") else "COSINE",
            },
        }
    except Exception:
        return {"exists": False, "points_count": 0}


def collection_exists(collection_name: str) -> bool:
    """Check if a collection exists."""
    client = get_client()
    if client is None:
        return False
    try:
        existing = {c.name for c in client.get_collections().collections}
        return collection_name in existing
    except Exception:
        return False


def get_all_collections() -> List[str]:
    """Return list of all collection names."""
    client = get_client()
    if client is None:
        return []
    try:
        return [c.name for c in client.get_collections().collections]
    except Exception:
        return []
