"""
Embedding engine — pluggable embedding providers.

Primary: FastEmbed BGE-small-en-v1.5 (384-dim).
Supports: OpenAI, Gemini, Nomic (abstract interface for future).
"""

from __future__ import annotations

import hashlib
import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from memory.models import EmbeddingProvider, EmbeddingResult
from memory.config import memory_config

logger = logging.getLogger(__name__)


# ── Abstract Base ────────────────────────────────────────────────────────

class BaseEmbeddingProvider(ABC):
    """Abstract base for embedding providers."""

    @abstractmethod
    def embed(self, texts: List[str]) -> List[EmbeddingResult]:
        """Generate embeddings for a list of texts."""
        ...

    @abstractmethod
    def embed_single(self, text: str) -> EmbeddingResult:
        """Generate embedding for a single text."""
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        ...

    @property
    @abstractmethod
    def dimension(self) -> int:
        ...


# ── FastEmbed Provider (primary) ────────────────────────────────────────

class FastEmbedProvider(BaseEmbeddingProvider):
    """FastEmbed embedding provider using BGE-small-en-v1.5."""

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5"):
        self._model_name = model_name
        self._model: Any = None
        self._dimension = 384

    def _ensure_model(self) -> Any:
        if self._model is None:
            from fastembed import TextEmbedding
            self._model = TextEmbedding(model_name=self._model_name)
        return self._model

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, texts: List[str]) -> List[EmbeddingResult]:
        if not texts:
            return []
        model = self._ensure_model()
        start = time.time()
        embeddings = list(model.embed(texts))
        elapsed_ms = (time.time() - start) * 1000
        per_text_ms = elapsed_ms / len(texts) if texts else 0
        return [
            EmbeddingResult(
                text=text,
                vector=[float(x) for x in emb],
                model=self._model_name,
                dimension=self._dimension,
                latency_ms=round(per_text_ms, 2),
            )
            for text, emb in zip(texts, embeddings)
        ]

    def embed_single(self, text: str) -> EmbeddingResult:
        results = self.embed([text])
        return results[0]


# ── Cache-Backed Provider ───────────────────────────────────────────────

class CachedEmbeddingProvider(BaseEmbeddingProvider):
    """Wraps any provider with an LRU-style hash cache."""

    def __init__(self, provider: BaseEmbeddingProvider, max_size: int = 1000):
        self._provider = provider
        self._cache: Dict[str, EmbeddingResult] = {}
        self._max_size = max_size

    @staticmethod
    def _cache_key(text: str, model: str) -> str:
        return hashlib.sha256(f"{model}:{text}".encode()).hexdigest()[:16]

    @property
    def model_name(self) -> str:
        return self._provider.model_name

    @property
    def dimension(self) -> int:
        return self._provider.dimension

    def embed(self, texts: List[str]) -> List[EmbeddingResult]:
        results: List[EmbeddingResult] = []
        uncached_texts: List[str] = []
        uncached_indices: List[int] = []

        for i, text in enumerate(texts):
            key = self._cache_key(text, self.model_name)
            if key in self._cache:
                results.append(self._cache[key])
            else:
                results.append(None)  # type: ignore
                uncached_texts.append(text)
                uncached_indices.append(i)

        if uncached_texts:
            fresh = self._provider.embed(uncached_texts)
            for idx, emb_result in zip(uncached_indices, fresh):
                results[idx] = emb_result
                key = self._cache_key(uncached_texts[uncached_indices.index(idx)], self.model_name)
                if len(self._cache) < self._max_size:
                    self._cache[key] = emb_result

        return results  # type: ignore

    def embed_single(self, text: str) -> EmbeddingResult:
        return self.embed([text])[0]

    def cache_size(self) -> int:
        return len(self._cache)

    def clear_cache(self) -> None:
        self._cache.clear()


# ── Factory ──────────────────────────────────────────────────────────────

def get_embedding_provider(
    provider: Optional[EmbeddingProvider] = None,
    use_cache: bool = True,
) -> BaseEmbeddingProvider:
    """Get the configured embedding provider, optionally wrapped with cache."""
    prov = provider or memory_config.embedding_provider

    if prov == EmbeddingProvider.FASTEMBED:
        base = FastEmbedProvider(model_name=memory_config.embedding_model)
    else:
        # Fallback to FastEmbed for unknown providers
        base = FastEmbedProvider(model_name=memory_config.embedding_model)

    if use_cache and memory_config.cache.enabled:
        return CachedEmbeddingProvider(base, max_size=memory_config.cache.embedding_cache_size)

    return base
