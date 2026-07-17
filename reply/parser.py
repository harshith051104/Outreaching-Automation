"""
Reply parser — cleans incoming email text for analysis.

Removes quoted history, signatures, disclaimers, and normalizes whitespace.
Deterministic — no AI calls.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from reply.models import ReplyRecord


# ── Signature patterns ──────────────────────────────────────────────────
_SIGNATURE_PATTERNS = [
    # Common email signatures
    re.compile(r"(?i)--\s*\n.*$", re.MULTILINE),
    re.compile(r"(?i)best\s*(regards|wishes|,\s*)$", re.MULTILINE),
    re.compile(r"(?i)kind\s*regards*,?\s*$", re.MULTILINE),
    re.compile(r"(?i)thanks\s*(and|&)?\s*(regards|best|,)\s*$", re.MULTILINE),
    re.compile(r"(?i)cheers,?\s*$", re.MULTILINE),
    re.compile(r"(?i)sent from my \w+", re.MULTILINE),
    re.compile(r"(?i)from:\s*.+\n.*sent:", re.MULTILINE | re.IGNORECASE),
    # Phone/address blocks
    re.compile(r"(?i)\+?\d[\d\s\-().]{7,}\d", re.MULTILINE),
    re.compile(r"(?i)\d+\s+\w+\s+(street|st|avenue|ave|road|rd|boulevard|blvd|drive|dr|lane|ln)\b.*$", re.MULTILINE),
]

# ── Disclaimer patterns ────────────────────────────────────────────────
_DISCLAIMER_PATTERNS = [
    re.compile(r"(?i)this email.*confidential.*", re.MULTILINE),
    re.compile(r"(?i)if you.*received.*in error.*", re.MULTILINE),
    re.compile(r"(?i)the information.*contained.*", re.MULTILINE),
    re.compile(r"(?i)unsubscribe.*", re.MULTILINE),
    re.compile(r"(?i)opt.out.*", re.MULTILINE),
]

# ── Quoted reply patterns ──────────────────────────────────────────────
_QUOTED_PATTERNS = [
    # "On [date], [name] wrote:" pattern
    re.compile(r"(?i)on\s+.+wrote:\s*\n.*", re.DOTALL),
    # Lines starting with >
    re.compile(r"(?:^>.*$\n?)+", re.MULTILINE),
    # -----Original Message-----
    re.compile(r"(?i)-+\s*original\s*message\s*-+.*", re.DOTALL),
    # -----Forwarded message-----
    re.compile(r"(?i)-+\s*forwarded\s*message\s*-+.*", re.DOTALL),
    # From: / Sent: / To: / Subject: header block at end
    re.compile(r"(?i)(?:from|sent|to|subject):\s+.*(?:\n|$)(?:(?:from|sent|to|subject):\s+.*(?:\n|$))*"),
]


def parse_reply(
    raw_body: str,
    sender: str = "",
    subject: str = "",
    thread_id: str = "",
    message_id: str = "",
    attachments: Optional[List[Dict[str, Any]]] = None,
) -> ReplyRecord:
    """
    Parse and clean a raw reply body.

    Returns a ReplyRecord with clean_text ready for intent analysis.
    """
    clean = _clean_text(raw_body)

    return ReplyRecord(
        sender_email=sender,
        subject=subject,
        raw_body=raw_body,
        clean_text=clean,
        gmail_thread_id=thread_id,
        gmail_message_id=message_id,
        attachments=attachments or [],
    )


def _clean_text(text: str) -> str:
    """Full cleaning pipeline: quotes → signatures → disclaimers → whitespace."""
    if not text:
        return ""

    # 1. Remove quoted reply content
    cleaned = _remove_quoted(text)
    # 2. Remove signatures
    cleaned = _remove_signatures(cleaned)
    # 3. Remove disclaimers
    cleaned = _remove_disclaimers(cleaned)
    # 4. Normalize whitespace
    cleaned = _normalize_whitespace(cleaned)
    # 5. Strip
    cleaned = cleaned.strip()

    return cleaned


def _remove_quoted(text: str) -> str:
    """Remove quoted reply/forwarded content."""
    result = text
    for pattern in _QUOTED_PATTERNS:
        result = pattern.sub("", result)
    return result


def _remove_signatures(text: str) -> str:
    """Remove email signatures."""
    result = text
    for pattern in _SIGNATURE_PATTERNS:
        result = pattern.sub("", result)
    return result


def _remove_disclaimers(text: str) -> str:
    """Remove legal disclaimers and footer text."""
    result = text
    for pattern in _DISCLAIMER_PATTERNS:
        result = pattern.sub("", result)
    return result


def _normalize_whitespace(text: str) -> str:
    """Collapse multiple blank lines and normalize spaces."""
    # Collapse 3+ newlines to 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Remove trailing whitespace on each line
    text = re.sub(r"[ \t]+$", "", text, flags=re.MULTILINE)
    return text
