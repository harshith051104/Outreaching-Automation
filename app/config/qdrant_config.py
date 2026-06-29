"""
Qdrant vector-store configuration.

Provides helpers to get a Qdrant client and lazily ensure that the required
collection (with the correct vector dimensionality) exists.
"""

from __future__ import annotations

import logging

from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams

from app.config.settings import settings

logger = logging.getLogger(__name__)

# Local fastembed BAAI/bge-small-en-v1.5 dimension
_VECTOR_SIZE: int = 384

# Module-level client cache
_qdrant_client: QdrantClient | None = None


def _get_qdrant_config_sync() -> tuple[str | None, str | None]:
    """Return Qdrant settings from environment only."""
    return settings.QDRANT_URL, settings.QDRANT_API_KEY


def get_qdrant_client() -> QdrantClient:
    """Return a (cached) Qdrant client pointed at the configured host/port or URL.
    
    If the remote Qdrant server is not reachable, falls back to a local
    persistent SQLite/file-based database in the storage directory to allow
    seamless offline/local development.
    """
    global _qdrant_client
    if _qdrant_client is None:
        try:
            url, api_key = _get_qdrant_config_sync()
            
            # Attempt to connect to remote Qdrant server
            if url:
                client = QdrantClient(
                    url=url,
                    api_key=api_key or None,
                    timeout=5.0,
                    check_compatibility=False,
                )
                display_dest = url
            else:
                client = QdrantClient(
                    host=settings.QDRANT_HOST,
                    port=settings.QDRANT_PORT,
                    timeout=5.0,
                    check_compatibility=False,
                )
                display_dest = f"{settings.QDRANT_HOST}:{settings.QDRANT_PORT}"
            # Verify connectivity by making a simple call
            client.get_collections()
            _qdrant_client = client
            logger.info("Qdrant client initialised (Remote Server) → %s", display_dest)
        except Exception as exc:
            import os
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            local_path = os.path.join(base_dir, "storage", "qdrant_local")
            os.makedirs(local_path, exist_ok=True)
            
            url, _ = _get_qdrant_config_sync()
            display_dest = url if url else f"{settings.QDRANT_HOST}:{settings.QDRANT_PORT}"
            logger.warning(
                "Could not connect to Qdrant server at %s (%s). "
                "Falling back to local persistent storage at '%s'.",
                display_dest,
                str(exc),
                local_path,
            )
            _qdrant_client = QdrantClient(path=local_path)
            logger.info("Qdrant client initialised (Local Persistent Mode) → %s", local_path)
            
    return _qdrant_client


def ensure_collection_exists(
    collection_name: str | None = None,
    vector_size: int = _VECTOR_SIZE,
) -> None:
    """Create the Qdrant collection if it does not already exist.

    Parameters
    ----------
    collection_name:
        Name of the collection. Defaults to ``settings.QDRANT_COLLECTION``.
    vector_size:
        Dimensionality of the vectors stored. Defaults to **1536** (OpenAI).
    """
    name = collection_name or settings.QDRANT_COLLECTION
    client = get_qdrant_client()

    existing = [c.name for c in client.get_collections().collections]
    if name in existing:
        logger.info("Qdrant collection '%s' already exists – skipping creation.", name)
        return

    client.create_collection(
        collection_name=name,
        vectors_config=VectorParams(
            size=vector_size,
            distance=Distance.COSINE,
        ),
    )
    logger.info(
        "Qdrant collection '%s' created (vector_size=%d, distance=COSINE).",
        name,
        vector_size,
    )
