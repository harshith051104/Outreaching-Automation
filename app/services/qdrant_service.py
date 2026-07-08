"""
Qdrant vector database service for semantic search and storage.

Uses FastEmbed BGE-small-en-v1.5 (384 dimensions) for embeddings.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

HAS_QDRANT = True

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models
    from qdrant_client.http.exceptions import UnexpectedResponse
    from app.config.settings import settings
    from app.config.qdrant_config import get_qdrant_client
    from fastembed import TextEmbedding

    _embedding_model: Optional[TextEmbedding] = None

    def get_embedding_model() -> TextEmbedding:
        global _embedding_model
        if _embedding_model is None:
            _embedding_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
        return _embedding_model

    def ensure_all_collections() -> None:
        """Create all required Qdrant collections if they don't exist."""
        client = get_qdrant_client()
        collections = ["campaigns", "leads", "emails", "replies", "signals", "company_research", "kb_documents"]

        existing = {c.name for c in client.get_collections().collections}

        for collection in collections:
            if collection not in existing:
                client.create_collection(
                    collection_name=collection,
                    vectors_config=models.VectorParams(
                        size=384,
                        distance=models.Distance.COSINE,
                    ),
                )
                logger.info(f"Created Qdrant collection: {collection}")

    async def store_document(
        collection_name: str,
        doc_id: str,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Store a document with embedding in Qdrant."""
        try:
            client = get_qdrant_client()
            model = get_embedding_model()

            # Generate embedding vector
            embeddings = list(model.embed([text]))
            vector = [float(x) for x in embeddings[0]]

            from qdrant_client.http.models import PointStruct

            # Store the original text in the metadata payload
            payload = metadata.copy() if metadata else {}
            payload["text"] = text

            point = PointStruct(
                id=doc_id,
                vector=vector,
                payload=payload,
            )

            client.upsert(
                collection_name=collection_name,
                points=[point],
            )
            return True
        except Exception as e:
            logger.error(f"Failed to store document in Qdrant: {e}")
            return False

    async def search_similar(
        collection_name: str,
        query: str,
        limit: int = 3,
    ) -> List[Dict[str, Any]]:
        """Search for similar documents in Qdrant."""
        try:
            client = get_qdrant_client()
            model = get_embedding_model()

            # Generate query embedding vector
            embeddings = list(model.embed([query]))
            query_vector = [float(x) for x in embeddings[0]]

            # Execute search based on available methods
            if hasattr(client, "query_points"):
                query_res = client.query_points(
                    collection_name=collection_name,
                    query=query_vector,
                    limit=limit,
                )
                results = query_res.points
            elif hasattr(client, "search"):
                results = client.search(
                    collection_name=collection_name,
                    query_vector=query_vector,
                    limit=limit,
                )
            else:
                results = client.query(
                    collection_name=collection_name,
                    query_text=query,
                    limit=limit,
                )

            formatted_results = []
            for hit in results:
                hit_id = getattr(hit, "id", None)
                score = getattr(hit, "score", 0.0)
                payload = getattr(hit, "payload", {}) or {}

                # Retrieve stored text. Handle legacy text if it was stored as string vector.
                text_content = payload.get("text", "")
                if not text_content:
                    vector_val = getattr(hit, "vector", None)
                    if isinstance(vector_val, str):
                        text_content = vector_val

                formatted_results.append({
                    "id": hit_id,
                    "text": text_content,
                    "score": score,
                    "metadata": payload,
                })

            return formatted_results
        except Exception as e:
            logger.error(f"Qdrant search failed: {e}")
            return []

except ImportError:
    HAS_QDRANT = False

    def get_qdrant_client():
        return None

    def ensure_all_collections():
        pass

    async def store_document(*args, **kwargs):
        return False

    async def search_similar(*args, **kwargs):
        return []