"""
Memory ingestion pipeline.

Imports knowledge from multiple sources into the vector store.
Each ingestion creates versioned memory records.
"""

from __future__ import annotations

import csv
import io
import logging
import time
from typing import Any, Dict, List, Optional

from memory.models import IngestionResult, MemoryRecord, MemoryStatus
from memory.config import memory_config
from memory.embedding_engine import get_embedding_provider
from memory.vector_store import upsert_batch, ensure_collection
from memory.metadata_manager import build_metadata
from memory.version_manager import create_version
from memory.logger import log_ingestion

logger = logging.getLogger(__name__)


def ingest_texts(
    collection: str,
    texts: List[str],
    metadata_list: Optional[List[Dict[str, Any]]] = None,
    batch_size: int = 50,
) -> IngestionResult:
    """
    Ingest a list of texts into a collection.

    Generates embeddings and stores with metadata.
    """
    start = time.time()
    if not texts:
        return IngestionResult(success=True, collection=collection, document_count=0)

    # Ensure collection exists
    coll_config = memory_config.get_collection(collection)
    if coll_config:
        ensure_collection(coll_config)

    provider = get_embedding_provider()
    total_stored = 0
    total_failed = 0
    errors: List[str] = []

    for i in range(0, len(texts), batch_size):
        batch_texts = texts[i : i + batch_size]
        batch_meta = metadata_list[i : i + batch_size] if metadata_list else [{}] * len(batch_texts)

        try:
            # Generate embeddings
            embeddings = provider.embed(batch_texts)

            # Build points
            points = []
            for text, emb, meta in zip(batch_texts, embeddings, batch_meta):
                record = MemoryRecord(
                    collection=collection,
                    text=text,
                    metadata=meta,
                    embedding_model=emb.model,
                    version=1,
                )
                create_version(record)

                payload = meta.copy()
                payload["text"] = text
                payload["embedding_model"] = emb.model
                points.append({
                    "id": record.memory_id,
                    "vector": emb.vector,
                    "payload": payload,
                })

            # Upsert to Qdrant
            stored = upsert_batch(collection, points, batch_size=batch_size)
            total_stored += stored
        except Exception as exc:
            total_failed += len(batch_texts)
            errors.append(str(exc))
            logger.error("Ingestion batch failed for %s: %s", collection, exc)

    elapsed_ms = (time.time() - start) * 1000
    log_ingestion(collection, total_stored, total_stored, elapsed_ms, total_failed)

    return IngestionResult(
        success=total_failed == 0,
        collection=collection,
        document_count=total_stored,
        embedding_count=total_stored,
        failed_count=total_failed,
        latency_ms=round(elapsed_ms, 2),
        errors=errors,
    )


def ingest_documents(
    collection: str,
    documents: List[Dict[str, Any]],
    text_key: str = "text",
    batch_size: int = 50,
) -> IngestionResult:
    """
    Ingest documents (dicts) into a collection.

    Each document must have a text_key field. Other fields become metadata.
    """
    texts = []
    metadata_list = []
    for doc in documents:
        text = doc.get(text_key, "")
        if not text:
            continue
        texts.append(text)
        meta = {k: v for k, v in doc.items() if k != text_key}
        metadata_list.append(meta)

    return ingest_texts(collection, texts, metadata_list, batch_size)


def ingest_csv(
    collection: str,
    csv_content: str,
    text_column: str,
    batch_size: int = 50,
) -> IngestionResult:
    """Ingest from CSV content string."""
    reader = csv.DictReader(io.StringIO(csv_content))
    documents = [row for row in reader]
    return ingest_documents(collection, documents, text_key=text_column, batch_size=batch_size)


def ingest_text_file(
    collection: str,
    content: str,
    filename: str = "",
    chunk_size: int = 1000,
    overlap: int = 200,
) -> IngestionResult:
    """Ingest a text file, chunking if necessary."""
    if len(content) <= chunk_size:
        return ingest_texts(
            collection,
            [content],
            [{"source": filename, "type": "document"}],
        )

    # Chunk with overlap
    chunks = []
    start = 0
    while start < len(content):
        end = start + chunk_size
        chunks.append(content[start:end])
        start = end - overlap
        if start + chunk_size > len(content) and end < len(content):
            chunks.append(content[end:])
            break

    metadata = [{"source": filename, "type": "document", "chunk_index": i} for i, _ in enumerate(chunks)]
    return ingest_texts(collection, chunks, metadata, batch_size=batch_size)


def ingest_lead(
    lead_id: str,
    name: str,
    role: str = "",
    company: str = "",
    campaign_id: str = "",
    user_id: str = "",
    extra: Optional[Dict[str, Any]] = None,
) -> IngestionResult:
    """Ingest a lead into the leads collection."""
    text = f"Lead: {name}, Role: {role}, Company: {company}"
    meta = build_metadata(
        collection="leads",
        source="lead_discovery",
        campaign_id=campaign_id,
        lead_id=lead_id,
        user_id=user_id,
        tags=["lead"],
        extra=extra or {},
    )
    return ingest_texts("leads", [text], [meta])


def ingest_email(
    email_id: str,
    subject: str,
    body: str,
    lead_id: str = "",
    campaign_id: str = "",
    user_id: str = "",
) -> IngestionResult:
    """Ingest a sent email."""
    text = f"Subject: {subject}\nBody: {body}"
    meta = build_metadata(
        collection="emails",
        source="email_delivery",
        campaign_id=campaign_id,
        lead_id=lead_id,
        user_id=user_id,
        tags=["email", "sent"],
    )
    return ingest_texts("emails", [text], [meta])


def ingest_reply(
    reply_id: str,
    reply_text: str,
    intent: str = "",
    sentiment: str = "",
    lead_id: str = "",
    campaign_id: str = "",
) -> IngestionResult:
    """Ingest a received reply."""
    meta = build_metadata(
        collection="replies",
        source="reply_monitor",
        campaign_id=campaign_id,
        lead_id=lead_id,
        tags=["reply"],
        extra={"intent": intent, "sentiment": sentiment},
    )
    return ingest_texts("replies", [reply_text], [meta])


def ingest_knowledge(
    doc_id: str,
    title: str,
    content: str,
    tags: Optional[List[str]] = None,
) -> IngestionResult:
    """Ingest a knowledge base document."""
    text = f"Title: {title}\nContent: {content}"
    meta = build_metadata(
        collection="knowledge",
        source="knowledge_base",
        tags=tags or ["knowledge"],
    )
    return ingest_texts("knowledge", [text], [meta])
