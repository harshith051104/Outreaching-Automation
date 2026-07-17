"""
Memory subsystem configuration.

Defines collection configs, embedding defaults, ranking weights, and retrieval params.
Mirrors memory_registry.yaml structure as Python dataclasses.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from memory.models import CollectionConfig, EmbeddingProvider


# ── Collection Definitions ──────────────────────────────────────────────

DEFAULT_COLLECTIONS: List[CollectionConfig] = [
    CollectionConfig(name="investors", vector_size=384, description="Investor profiles, theses, portfolio companies"),
    CollectionConfig(name="companies", vector_size=384, description="Company knowledge, product info"),
    CollectionConfig(name="campaigns", vector_size=384, description="Campaign configs, generated artifacts, execution history"),
    CollectionConfig(name="emails", vector_size=384, description="Sent emails, templates, personalization history"),
    CollectionConfig(name="replies", vector_size=384, description="Parsed replies, intent analysis, summaries"),
    CollectionConfig(name="signals", vector_size=384, description="Signal intelligence events and hooks"),
    CollectionConfig(name="templates", vector_size=384, description="Email templates and prompt templates"),
    CollectionConfig(name="documents", vector_size=384, description="Uploaded documents, research reports"),
    CollectionConfig(name="crm", vector_size=384, description="CRM records and contact data"),
    CollectionConfig(name="knowledge", vector_size=384, description="Knowledge base articles and reference docs"),
    CollectionConfig(name="notes", vector_size=384, description="Manual notes and annotations"),
    CollectionConfig(name="company_research", vector_size=384, description="Research agent outputs"),
    CollectionConfig(name="kb_documents", vector_size=384, description="Knowledge base document embeddings"),
    CollectionConfig(name="linkedin_outreach", vector_size=384, description="LinkedIn outreach history and conversations"),
]

COLLECTION_MAP: Dict[str, CollectionConfig] = {c.name: c for c in DEFAULT_COLLECTIONS}

# ── Ranking Formula ─────────────────────────────────────────────────────

@dataclass
class RankingConfig:
    similarity_weight: float = 0.5
    recency_weight: float = 0.3
    campaign_match_weight: float = 0.2
    recency_decay_rate: float = 0.01


# ── Retrieval Defaults ──────────────────────────────────────────────────

@dataclass
class RetrievalConfig:
    default_limit: int = 3
    score_threshold: float = 0.3
    enable_hybrid: bool = True
    hybrid_alpha: float = 0.7  # weight for vector vs keyword in hybrid
    max_context_items: int = 10
    max_context_age_days: int = 30


# ── Cache Config ────────────────────────────────────────────────────────

@dataclass
class CacheConfig:
    enabled: bool = True
    embedding_cache_size: int = 1000
    search_cache_size: int = 500
    search_cache_ttl_seconds: int = 300


# ── Lifecycle Config ────────────────────────────────────────────────────

@dataclass
class LifecycleConfig:
    auto_expire: bool = True
    reindex_interval_hours: int = 24
    archive_after_days: int = 90
    max_versions_per_memory: int = 10


# ── Security Config ─────────────────────────────────────────────────────

@dataclass
class SecurityConfig:
    enforce_user_isolation: bool = True
    enforce_workspace_isolation: bool = True
    enforce_campaign_isolation: bool = True


# ── Memory Config (top-level) ──────────────────────────────────────────

@dataclass
class MemoryConfig:
    """Top-level configuration for the memory subsystem."""
    # Embedding
    embedding_provider: EmbeddingProvider = EmbeddingProvider.FASTEMBED
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dimension: int = 384

    # Collections
    collections: List[CollectionConfig] = field(default_factory=lambda: list(DEFAULT_COLLECTIONS))

    # Ranking
    ranking: RankingConfig = field(default_factory=RankingConfig)

    # Retrieval
    retrieval: RetrievalConfig = field(default_factory=RetrievalConfig)

    # Cache
    cache: CacheConfig = field(default_factory=CacheConfig)

    # Lifecycle
    lifecycle: LifecycleConfig = field(default_factory=LifecycleConfig)

    # Security
    security: SecurityConfig = field(default_factory=SecurityConfig)

    # Qdrant connection (mirrors app.config.settings)
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_url: str = ""
    qdrant_api_key: str = ""

    def get_collection(self, name: str) -> Optional[CollectionConfig]:
        return COLLECTION_MAP.get(name)

    def get_collection_names(self) -> List[str]:
        return [c.name for c in self.collections]


# Module-level singleton
memory_config = MemoryConfig()
