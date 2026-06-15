"""
Unique ID generation utilities for all entity types.

Provides UUID-based ID generators for database documents,
and a shorter tracking ID for email tracking URLs.
"""

import uuid


def generate_id() -> str:
    """
    Generate a standard UUID4 string for use as a document ID.

    Returns:
        A random UUID4 string (36 chars with hyphens).
    """
    return str(uuid.uuid4())


def generate_tracking_id() -> str:
    """
    Generate a URL-safe tracking ID for email open/click tracking.

    Uses UUID4 but strips hyphens for compactness in URLs.
    The resulting ID is 32 alphanumeric characters.

    Returns:
        A compact UUID4 string without hyphens.
    """
    return uuid.uuid4().hex


def generate_short_id(length: int = 8) -> str:
    """
    Generate a short random alphanumeric ID.

    Useful for referral codes, short links, etc.

    Args:
        length: Number of characters (default 8).

    Returns:
        Random alphanumeric string of specified length.
    """
    return uuid.uuid4().hex[:length]