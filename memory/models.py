"""
Memory subsystem data models.

All types used across the memory infrastructure: records, search results,
collection configs, embedding results, ingestion results.
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# ── Enums ────────────────────────────────────────────────────────────────

class MemoryStatus(str, enum.Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"
    EXPIRED = "expired"


class EmbeddingProvider(str, enum.Enum):
    FASTEMBED = "fastembed"
    OPENAI = "openai"
    GEMINI = "gemini"
    BGE = "bge"
    NOMIC = "nomic"


# ── Collection Config ───────────────────────────────────────────────────

@dataclass
class CollectionConfig:
    """Configuration for a single Qdrant collection."""
    name: str
    vector_size: int = 384
    distance: str = "COSINE"
    description: str = ""
    indexes: List[str] = field(default_factory=list)
    ttl_days: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "vector_size": self.vector_size,
            "distance": self.distance,
            "description": self.description,
            "indexes": self.indexes,
            "ttl_days": self.ttl_days,
        }


# ── Memory Record ───────────────────────────────────────────────────────

@dataclass
class MemoryRecord:
    """A single memory stored in the vector database."""
    memory_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    collection: str = ""
    text: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    vector: Optional[List[float]] = None
    source: str = ""
    campaign_id: str = ""
    lead_id: str = ""
    user_id: str = ""
    tags: List[str] = field(default_factory=list)
    version: int = 1
    status: MemoryStatus = MemoryStatus.ACTIVE
    embedding_model: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    expires_at: Optional[str] = None

    def to_doc(self) -> Dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "collection": self.collection,
            "text": self.text,
            "metadata": self.metadata,
            "source": self.source,
            "campaign_id": self.campaign_id,
            "lead_id": self.lead_id,
            "user_id": self.user_id,
            "tags": self.tags,
            "version": self.version,
            "status": self.status.value,
            "embedding_model": self.embedding_model,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "expires_at": self.expires_at,
        }

    @classmethod
    def from_doc(cls, doc: Dict[str, Any]) -> MemoryRecord:
        return cls(
            memory_id=doc.get("memory_id", str(uuid.uuid4())),
            collection=doc.get("collection", ""),
            text=doc.get("text", ""),
            metadata=doc.get("metadata", {}),
            source=doc.get("source", ""),
            campaign_id=doc.get("campaign_id", ""),
            lead_id=doc.get("lead_id", ""),
            user_id=doc.get("user_id", ""),
            tags=doc.get("tags", []),
            version=doc.get("version", 1),
            status=MemoryStatus(doc.get("status", "active")),
            embedding_model=doc.get("embedding_model", ""),
            created_at=doc.get("created_at", ""),
            updated_at=doc.get("updated_at", ""),
            expires_at=doc.get("expires_at"),
        )


# ── Embedding Result ────────────────────────────────────────────────────

@dataclass
class EmbeddingResult:
    """Result from the embedding engine."""
    text: str
    vector: List[float]
    model: str
    dimension: int
    latency_ms: float = 0.0


# ── Search Result ────────────────────────────────────────────────────────

@dataclass
class SearchResult:
    """A single result from the retrieval engine."""
    memory_id: str
    text: str
    score: float
    collection: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    rank: int = 0
    # Ranking breakdown
    similarity_score: float = 0.0
    recency_score: float = 0.0
    campaign_match_score: float = 0.0
    source_priority_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "text": self.text,
            "score": self.score,
            "collection": self.collection,
            "metadata": self.metadata,
            "rank": self.rank,
            "similarity_score": self.similarity_score,
            "recency_score": self.recency_score,
            "campaign_match_score": self.campaign_match_score,
            "source_priority_score": self.source_priority_score,
        }


# ── Ingestion Result ────────────────────────────────────────────────────

@dataclass
class IngestionResult:
    """Result from an ingestion operation."""
    success: bool
    collection: str
    document_count: int = 0
    embedding_count: int = 0
    failed_count: int = 0
    latency_ms: float = 0.0
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "collection": self.collection,
            "document_count": self.document_count,
            "embedding_count": self.embedding_count,
            "failed_count": self.failed_count,
            "latency_ms": self.latency_ms,
            "errors": self.errors,
        }


# ── Context Package ─────────────────────────────────────────────────────

@dataclass
class ContextPackage:
    """Structured AI context assembled from retrieved memories."""
    query: str
    investor: Dict[str, Any] = field(default_factory=dict)
    company: Dict[str, Any] = field(default_factory=dict)
    portfolio: List[Dict[str, Any]] = field(default_factory=list)
    campaign: Dict[str, Any] = field(default_factory=dict)
    recent_emails: List[Dict[str, Any]] = field(default_factory=list)
    past_replies: List[Dict[str, Any]] = field(default_factory=list)
    knowledge: List[Dict[str, Any]] = field(default_factory=list)
    signals: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "investor": self.investor,
            "company": self.company,
            "portfolio": self.portfolio,
            "campaign": self.campaign,
            "recent_emails": self.recent_emails,
            "past_replies": self.past_replies,
            "knowledge": self.knowledge,
            "signals": self.signals,
            "metadata": self.metadata,
        }


# ── Version Record ──────────────────────────────────────────────────────

@dataclass
class VersionRecord:
    """Tracks version history for a memory."""
    memory_id: str
    version: int
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    is_current: bool = True

    def to_doc(self) -> Dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "version": self.version,
            "text": self.text,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "is_current": self.is_current,
        }


# ── Analytics Snapshot ──────────────────────────────────────────────────

@dataclass
class AnalyticsSnapshot:
    """Point-in-time analytics for the memory subsystem."""
    collection_sizes: Dict[str, int] = field(default_factory=dict)
    total_embeddings: int = 0
    search_count: int = 0
    avg_search_latency_ms: float = 0.0
    cache_hit_ratio: float = 0.0
    cache_miss_ratio: float = 0.0
    index_optimization_status: str = "ok"
    snapshot_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "collection_sizes": self.collection_sizes,
            "total_embeddings": self.total_embeddings,
            "search_count": self.search_count,
            "avg_search_latency_ms": self.avg_search_latency_ms,
            "cache_hit_ratio": self.cache_hit_ratio,
            "cache_miss_ratio": self.cache_miss_ratio,
            "index_optimization_status": self.index_optimization_status,
            "snapshot_at": self.snapshot_at,
        }
