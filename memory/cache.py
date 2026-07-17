"""
Search result and embedding cache.

LRU cache with TTL for search results, hash-based cache for embeddings.
"""

from __future__ import annotations

import hashlib
import time
from collections import OrderedDict
from threading import Lock
from typing import Any, Dict, List, Optional

from memory.config import memory_config


class EmbeddingCache:
    """Hash-based cache for embedding vectors."""

    def __init__(self, max_size: int = 1000):
        self._cache: OrderedDict[str, List[float]] = OrderedDict()
        self._max_size = max_size
        self._lock = Lock()
        self._hits = 0
        self._misses = 0

    @staticmethod
    def _key(text: str, model: str) -> str:
        return hashlib.sha256(f"{model}:{text}".encode()).hexdigest()[:16]

    def get(self, text: str, model: str) -> Optional[List[float]]:
        key = self._key(text, model)
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                self._hits += 1
                return self._cache[key]
            self._misses += 1
            return None

    def set(self, text: str, model: str, vector: List[float]) -> None:
        key = self._key(text, model)
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = vector
            if len(self._cache) > self._max_size:
                self._cache.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0

    def stats(self) -> Dict[str, Any]:
        total = self._hits + self._misses
        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_ratio": self._hits / total if total > 0 else 0.0,
        }


class SearchCache:
    """TTL-based cache for search results."""

    def __init__(self, max_size: int = 500, ttl_seconds: int = 300):
        self._cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._max_size = max_size
        self._ttl = ttl_seconds
        self._lock = Lock()
        self._hits = 0
        self._misses = 0

    @staticmethod
    def _key(collection: str, query: str, limit: int, filters_hash: str = "") -> str:
        raw = f"{collection}:{query}:{limit}:{filters_hash}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def get(self, collection: str, query: str, limit: int, filters_hash: str = "") -> Optional[List[Dict[str, Any]]]:
        key = self._key(collection, query, limit, filters_hash)
        with self._lock:
            if key in self._cache:
                entry = self._cache[key]
                if time.time() - entry["ts"] < self._ttl:
                    self._cache.move_to_end(key)
                    self._hits += 1
                    return entry["results"]
                else:
                    del self._cache[key]
            self._misses += 1
            return None

    def set(self, collection: str, query: str, limit: int, results: List[Dict[str, Any]], filters_hash: str = "") -> None:
        key = self._key(collection, query, limit, filters_hash)
        with self._lock:
            self._cache[key] = {"results": results, "ts": time.time()}
            if len(self._cache) > self._max_size:
                self._cache.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0

    def stats(self) -> Dict[str, Any]:
        total = self._hits + self._misses
        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_ratio": self._hits / total if total > 0 else 0.0,
            "ttl_seconds": self._ttl,
        }


# Module-level singletons
embedding_cache = EmbeddingCache(max_size=memory_config.cache.embedding_cache_size)
search_cache = SearchCache(
    max_size=memory_config.cache.search_cache_size,
    ttl_seconds=memory_config.cache.search_cache_ttl_seconds,
)
