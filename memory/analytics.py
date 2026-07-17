"""
Memory analytics — collection metrics, search latency, cache stats.

Tracks operational metrics for dashboards and monitoring.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional

from memory.models import AnalyticsSnapshot
from memory.config import memory_config
from memory.vector_store import get_collection_info, get_all_collections
from memory.cache import embedding_cache, search_cache

logger = logging.getLogger(__name__)

# In-memory counters (production would use Prometheus/StatsD)
_search_latencies: Dict[str, List[float]] = defaultdict(list)
_ingestion_counts: Dict[str, int] = defaultdict(int)
_total_searches = 0
_total_embeddings = 0


def record_search_latency(collection: str, latency_ms: float) -> None:
    _search_latencies[collection].append(latency_ms)
    global _total_searches
    _total_searches += 1


def record_ingestion(collection: str, count: int) -> None:
    _ingestion_counts[collection] += count
    global _total_embeddings
    _total_embeddings += count


def get_snapshot() -> AnalyticsSnapshot:
    """Get a point-in-time analytics snapshot."""
    collections = get_all_collections()
    sizes = {}
    total_points = 0
    for coll in collections:
        info = get_collection_info(coll)
        count = info.get("points_count", 0)
        sizes[coll] = count
        total_points += count

    # Compute average search latency
    all_latencies = []
    for latencies in _search_latencies.values():
        all_latencies.extend(latencies[-100:])  # last 100 per collection
    avg_latency = sum(all_latencies) / len(all_latencies) if all_latencies else 0.0

    emb_stats = embedding_cache.stats()
    search_stats = search_cache.stats()

    return AnalyticsSnapshot(
        collection_sizes=sizes,
        total_embeddings=total_points,
        search_count=_total_searches,
        avg_search_latency_ms=round(avg_latency, 2),
        cache_hit_ratio=emb_stats["hit_ratio"],
        cache_miss_ratio=1.0 - emb_stats["hit_ratio"],
    )


def get_collection_analytics(collection: str) -> Dict[str, Any]:
    """Get analytics for a single collection."""
    info = get_collection_info(collection)
    latencies = _search_latencies.get(collection, [])
    avg_lat = sum(latencies[-100:]) / len(latencies[-100:]) if latencies else 0.0

    return {
        "collection": collection,
        "points_count": info.get("points_count", 0),
        "exists": info.get("exists", False),
        "search_count": len(latencies),
        "avg_search_latency_ms": round(avg_lat, 2),
        "ingestion_count": _ingestion_counts.get(collection, 0),
    }


def reset_counters() -> None:
    """Reset all counters (for testing)."""
    global _total_searches, _total_embeddings
    _search_latencies.clear()
    _ingestion_counts.clear()
    _total_searches = 0
    _total_embeddings = 0
