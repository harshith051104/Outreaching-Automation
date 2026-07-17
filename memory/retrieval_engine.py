"""
Retrieval engine — semantic + hybrid search with metadata filtering.

Unified interface for all retrieval operations across collections.
"""

from __future__ import annotations

import hashlib
import logging
import math
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from memory.models import SearchResult
from memory.config import memory_config
from memory.embedding_engine import get_embedding_provider
from memory.vector_store import search as vector_search
from memory.cache import search_cache
from memory.logger import log_search

logger = logging.getLogger(__name__)


def _filters_hash(filters: Optional[Dict[str, Any]]) -> str:
    if not filters:
        return ""
    raw = str(sorted(filters.items()))
    return hashlib.sha256(raw.encode()).hexdigest()[:8]


def search(
    query: str,
    collection: str,
    limit: int = 3,
    score_threshold: Optional[float] = None,
    filters: Optional[Dict[str, Any]] = None,
    use_cache: bool = True,
) -> List[SearchResult]:
    """
    Semantic search with optional metadata filtering.

    Args:
        query: Search text.
        collection: Qdrant collection name.
        limit: Max results.
        score_threshold: Minimum similarity score.
        filters: Metadata filter dict.
        use_cache: Whether to use search cache.

    Returns:
        List of SearchResult sorted by score descending.
    """
    start = time.time()
    fhash = _filters_hash(filters)

    # Check cache
    if use_cache and memory_config.cache.enabled:
        cached = search_cache.get(collection, query, limit, fhash)
        if cached is not None:
            return [SearchResult(**r) if isinstance(r, dict) else r for r in cached]

    # Generate query embedding
    provider = get_embedding_provider()
    emb_result = provider.embed_single(query)
    query_vector = emb_result.vector

    # Build Qdrant filter
    qdrant_filter = _build_filter(filters) if filters else None

    # Execute search
    raw_results = vector_search(
        collection_name=collection,
        query_vector=query_vector,
        limit=limit,
        score_threshold=score_threshold or memory_config.retrieval.score_threshold,
        query_filter=qdrant_filter,
    )

    # Convert to SearchResult
    results = []
    for i, hit in enumerate(raw_results):
        meta = hit.get("metadata", {})
        results.append(SearchResult(
            memory_id=hit.get("id", ""),
            text=hit.get("text", ""),
            score=hit.get("score", 0.0),
            collection=collection,
            metadata=meta,
            rank=i + 1,
            similarity_score=hit.get("score", 0.0),
        ))

    elapsed_ms = (time.time() - start) * 1000
    log_search(collection, len(results), elapsed_ms, score_threshold or memory_config.retrieval.score_threshold)

    # Cache results
    if use_cache and memory_config.cache.enabled:
        search_cache.set(collection, query, limit, [r.to_dict() for r in results], fhash)

    return results


def search_multi(
    query: str,
    collections: List[str],
    limit: int = 3,
    score_threshold: Optional[float] = None,
    filters: Optional[Dict[str, Any]] = None,
) -> Dict[str, List[SearchResult]]:
    """Search across multiple collections."""
    return {
        coll: search(query, coll, limit, score_threshold, filters)
        for coll in collections
    }


def ranked_search(
    query: str,
    collection: str,
    limit: int = 3,
    current_campaign_id: Optional[str] = None,
    filters: Optional[Dict[str, Any]] = None,
) -> List[SearchResult]:
    """
    Search with multi-factor ranking: similarity + recency + campaign match.
    Mirrors the ranking formula from memory_service.py.
    """
    # Fetch more candidates for re-ranking
    candidates = search(query, collection, limit=limit * 3, filters=filters)
    if not candidates:
        return []

    now = datetime.now(timezone.utc)
    weights = memory_config.ranking
    ranked: List[SearchResult] = []

    for r in candidates:
        meta = r.metadata

        # Recency score
        recency = 1.0
        created_at_str = meta.get("created_at")
        if created_at_str:
            try:
                created_at = datetime.fromisoformat(created_at_str)
                days = max(0.0, (now - created_at).total_seconds() / 86400.0)
                recency = math.exp(-weights.recency_decay_rate * days)
            except Exception:
                pass

        # Campaign match score
        campaign_match = 0.0
        item_campaign = meta.get("campaign_id")
        if current_campaign_id and item_campaign:
            if item_campaign == current_campaign_id:
                campaign_match = 1.0

        # Final weighted score
        final = (
            r.similarity_score * weights.similarity_weight
            + recency * weights.recency_weight
            + campaign_match * weights.campaign_match_weight
        )

        r.recency_score = recency
        r.campaign_match_score = campaign_match
        r.score = round(final, 4)
        ranked.append(r)

    ranked.sort(key=lambda x: x.score, reverse=True)
    for i, r in enumerate(ranked[:limit]):
        r.rank = i + 1
    return ranked[:limit]


def _build_filter(filters: Dict[str, Any]) -> Any:
    """Convert filter dict to Qdrant Filter object."""
    if not filters:
        return None

    try:
        from qdrant_client.http.models import Filter, FieldCondition, MatchValue

        conditions = []
        for key, value in filters.items():
            if isinstance(value, list):
                # OR condition for list values
                or_conditions = [FieldCondition(key=key, match=MatchValue(value=v)) for v in value]
                if len(or_conditions) == 1:
                    conditions.append(or_conditions[0])
                else:
                    from qdrant_client.http.models import Should
                    conditions.append(Should(should=or_conditions))
            else:
                conditions.append(FieldCondition(key=key, match=MatchValue(value=value)))

        if not conditions:
            return None
        if len(conditions) == 1:
            return Filter(must=[conditions[0]] if not isinstance(conditions[0], Should) else Filter(should=[conditions[0]]))
        return Filter(must=conditions)
    except Exception as exc:
        logger.warning("Failed to build Qdrant filter: %s", exc)
        return None
