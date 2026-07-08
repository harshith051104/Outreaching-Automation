"""
Security utilities — centralized Fernet-based symmetric encryption.

All secrets (API keys, OAuth tokens, session cookies) stored in the
``user_integrations`` collection are encrypted/decrypted here.

The encryption key is derived from ``COOKIE_ENCRYPTION_KEY`` or
``JWT_SECRET`` in settings (the same derivation previously scattered
across linkedin_outreach_service.py is now consolidated here).
"""

from __future__ import annotations

import base64
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

_fernet_instance: Fernet | None = None


def _get_fernet() -> Fernet:
    """Build (and cache) the Fernet instance from application settings."""
    global _fernet_instance
    if _fernet_instance is not None:
        return _fernet_instance

    from app.config.settings import settings  # local import to avoid circular deps

    raw_key = getattr(settings, "COOKIE_ENCRYPTION_KEY", None) or getattr(
        settings, "JWT_SECRET", None
    )
    if not raw_key:
        raise RuntimeError(
            "No encryption key found. Set COOKIE_ENCRYPTION_KEY or JWT_SECRET in .env"
        )

    # Derive a 32-byte key and base64-url-encode it for Fernet
    derived = hashlib.sha256(raw_key.encode()).digest()
    fernet_key = base64.urlsafe_b64encode(derived)
    _fernet_instance = Fernet(fernet_key)
    return _fernet_instance


def encrypt_secret(plaintext: str) -> str:
    """
    Encrypt a plaintext string and return a base64-encoded ciphertext string.

    Args:
        plaintext: The secret value to encrypt (e.g., an API key).

    Returns:
        A URL-safe base64 string that can be safely stored in MongoDB.
    """
    if not plaintext:
        return ""
    fernet = _get_fernet()
    token = fernet.encrypt(plaintext.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_secret(ciphertext: str) -> str:
    """
    Decrypt a ciphertext string previously produced by ``encrypt_secret``.

    Args:
        ciphertext: The encrypted token string.

    Returns:
        The original plaintext string.

    Raises:
        ValueError: If the ciphertext is invalid or was encrypted with a
                    different key.
    """
    if not ciphertext:
        return ""
    fernet = _get_fernet()
    try:
        return fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        logger.error("Failed to decrypt secret — token invalid or key mismatch.")
        raise ValueError("Could not decrypt secret. Token may be corrupted.") from exc


def encrypt_dict(data: dict) -> dict:
    """
    Encrypt all string values in a flat dict.

    Useful for storing provider credential payloads (e.g. api_key, client_id).
    Non-string values are left unchanged.
    """
    return {
        k: (encrypt_secret(v) if isinstance(v, str) and v else v)
        for k, v in data.items()
    }


def decrypt_dict(data: dict) -> dict:
    """
    Decrypt all string values in a flat dict.

    Reverses ``encrypt_dict``.
    """
    result = {}
    for k, v in data.items():
        if isinstance(v, str) and v:
            try:
                result[k] = decrypt_secret(v)
            except ValueError:
                result[k] = v  # return as-is if decryption fails
        else:
            result[k] = v
    return result


def reset_fernet_cache() -> None:
    """Reset the cached Fernet instance (used in tests)."""
    global _fernet_instance
    _fernet_instance = None


def sanitize_nosql(data: Any) -> Any:
    """
    Recursively remove/sanitize keys starting with '$' to prevent MongoDB operator injection.
    ponytail: Simple recursive dict filter.
    """
    from typing import Any as AnyType
    if isinstance(data, dict):
        return {
            k: sanitize_nosql(v)
            for k, v in data.items()
            if not str(k).startswith("$")
        }
    elif isinstance(data, list):
        return [sanitize_nosql(v) for v in data]
    return data
