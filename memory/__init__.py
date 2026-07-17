"""
RAG Vector Memory Infrastructure.

Centralized knowledge layer for the entire outreach platform.
"""

from memory.models import (
    MemoryRecord,
    MemoryStatus,
    EmbeddingProvider,
    EmbeddingResult,
    SearchResult,
    IngestionResult,
    ContextPackage,
    CollectionConfig,
    VersionRecord,
    AnalyticsSnapshot,
)
from memory.config import MemoryConfig, memory_config, COLLECTION_MAP
from memory.embedding_engine import get_embedding_provider, BaseEmbeddingProvider
from memory.vector_store import (
    ensure_all_collections,
    ensure_collection,
    upsert_point,
    upsert_batch,
    search,
    delete_point,
    delete_batch,
    get_collection_info,
    collection_exists,
    get_all_collections,
    get_client,
)
from memory.retrieval_engine import search as retrieval_search, search_multi, ranked_search
from memory.context_builder import (
    build_context,
    build_investor_context,
    build_campaign_context,
    context_to_prompt,
)
from memory.ingestion import (
    ingest_texts,
    ingest_documents,
    ingest_csv,
    ingest_text_file,
    ingest_lead,
    ingest_email,
    ingest_reply,
    ingest_knowledge,
)
from memory.version_manager import (
    create_version,
    get_current_version,
    get_version_history,
    rollback,
    soft_delete,
    restore,
    prune_old_versions,
)
from memory.cache import embedding_cache, search_cache
from memory.lifecycle import (
    create_memory,
    update_memory,
    archive_memory,
    delete_memory,
    expire_memories,
    reindex_collection,
    get_memory_stats,
)
from memory.analytics import get_snapshot, get_collection_analytics
from memory.security import AccessContext, can_read, can_write, apply_security_filter

__all__ = [
    # Models
    "MemoryRecord", "MemoryStatus", "EmbeddingProvider", "EmbeddingResult",
    "SearchResult", "IngestionResult", "ContextPackage", "CollectionConfig",
    "VersionRecord", "AnalyticsSnapshot",
    # Config
    "MemoryConfig", "memory_config", "COLLECTION_MAP",
    # Embedding
    "get_embedding_provider", "BaseEmbeddingProvider",
    # Vector store
    "ensure_all_collections", "ensure_collection", "upsert_point", "upsert_batch",
    "search", "delete_point", "delete_batch", "get_collection_info",
    "collection_exists", "get_all_collections", "get_client",
    # Retrieval
    "retrieval_search", "search_multi", "ranked_search",
    # Context
    "build_context", "build_investor_context", "build_campaign_context", "context_to_prompt",
    # Ingestion
    "ingest_texts", "ingest_documents", "ingest_csv", "ingest_text_file",
    "ingest_lead", "ingest_email", "ingest_reply", "ingest_knowledge",
    # Versioning
    "create_version", "get_current_version", "get_version_history",
    "rollback", "soft_delete", "restore", "prune_old_versions",
    # Cache
    "embedding_cache", "search_cache",
    # Lifecycle
    "create_memory", "update_memory", "archive_memory", "delete_memory",
    "expire_memories", "reindex_collection", "get_memory_stats",
    # Analytics
    "get_snapshot", "get_collection_analytics",
    # Security
    "AccessContext", "can_read", "can_write", "apply_security_filter",
]
