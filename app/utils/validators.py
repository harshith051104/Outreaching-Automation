"""
Email address and URL validation utilities.

Uses Python's built-in validation where possible to avoid heavy dependencies.
"""

import re
from typing import Optional


_EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
)


def validate_email_format(email: str) -> bool:
    """
    Validate an email address format.

    Args:
        email: Email address string to validate.

    Returns:
        True if the email format is valid, False otherwise.
    """
    if not email or not isinstance(email, str):
        return False
    return bool(_EMAIL_REGEX.match(email.strip()))


def validate_url(url: str) -> bool:
    """
    Validate a URL format (http or https).

    Args:
        url: URL string to validate.

    Returns:
        True if the URL format is valid, False otherwise.
    """
    if not url or not isinstance(url, str):
        return False
    url = url.strip()
    return bool(
        re.match(r"^https?://", url)
        and len(url) > 7
        and not url.count(" ") > 0
    )


def sanitize_email(email: str) -> str:
    """
    Sanitize and normalize an email address.

    Args:
        email: Email address to sanitize.

    Returns:
        Lowercase, stripped email address.
    """
    return email.lower().strip()