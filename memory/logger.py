"""
Structured logging for the memory subsystem.

Provides a consistent logging interface with execution tracking.
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Any, Dict, Generator, Optional


_logger = logging.getLogger("memory")


def get_logger(name: str = "memory") -> logging.Logger:
    return logging.getLogger(name)


@contextmanager
def log_operation(
    operation: str,
    collection: str = "",
    execution_id: str = "",
    **extra: Any,
) -> Generator[Dict[str, Any], None, None]:
    """Context manager that logs start/end/latency of an operation."""
    logger = get_logger()
    start = time.time()
    context: Dict[str, Any] = {
        "operation": operation,
        "collection": collection,
        "execution_id": execution_id,
        **extra,
    }
    logger.info(
        "memory.operation.start",
        extra={"memory_ctx": context},
    )
    try:
        yield context
        elapsed_ms = (time.time() - start) * 1000
        context["latency_ms"] = round(elapsed_ms, 2)
        context["status"] = "success"
        logger.info(
            "memory.operation.end",
            extra={"memory_ctx": context},
        )
    except Exception as exc:
        elapsed_ms = (time.time() - start) * 1000
        context["latency_ms"] = round(elapsed_ms, 2)
        context["status"] = "error"
        context["error"] = str(exc)
        logger.error(
            "memory.operation.error",
            extra={"memory_ctx": context},
        )
        raise


def log_embedding(
    model: str,
    text_count: int,
    dimension: int,
    latency_ms: float,
    cached: int = 0,
) -> None:
    get_logger().info(
        "memory.embedding",
        extra={
            "model": model,
            "text_count": text_count,
            "dimension": dimension,
            "latency_ms": round(latency_ms, 2),
            "cached": cached,
        },
    )


def log_search(
    collection: str,
    result_count: int,
    latency_ms: float,
    score_threshold: float = 0.0,
    hybrid: bool = False,
) -> None:
    get_logger().info(
        "memory.search",
        extra={
            "collection": collection,
            "result_count": result_count,
            "latency_ms": round(latency_ms, 2),
            "score_threshold": score_threshold,
            "hybrid": hybrid,
        },
    )


def log_ingestion(
    collection: str,
    document_count: int,
    embedding_count: int,
    latency_ms: float,
    errors: int = 0,
) -> None:
    get_logger().info(
        "memory.ingestion",
        extra={
            "collection": collection,
            "document_count": document_count,
            "embedding_count": embedding_count,
            "latency_ms": round(latency_ms, 2),
            "errors": errors,
        },
    )


def log_cache_hit(key: str, cache_type: str = "search") -> None:
    get_logger().debug(
        "memory.cache.hit",
        extra={"key": key, "cache_type": cache_type},
    )


def log_cache_miss(key: str, cache_type: str = "search") -> None:
    get_logger().debug(
        "memory.cache.miss",
        extra={"key": key, "cache_type": cache_type},
    )
