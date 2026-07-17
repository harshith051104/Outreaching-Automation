"""
Sentiment analysis — determines reply tone independent of intent.

Deterministic + optional LLM enhancement. Returns Sentiment enum + confidence.
"""

from __future__ import annotations

import re
from typing import Tuple

from reply.models import Sentiment
from reply.config import reply_config


# ── Keyword-based sentiment (fast, no LLM) ─────────────────────────────
_POSITIVE_KEYWORDS = [
    "thank", "thanks", "appreciate", "great", "excellent", "love", "excited",
    "interested", "sounds good", "let's do", "happy to", "glad", "wonderful",
    "fantastic", "impressed", "looking forward", "absolutely", "definitely",
    "yes", "sure", "perfect", "amazing", "awesome", "brilliant",
]

_NEGATIVE_KEYWORDS = [
    "not interested", "no thanks", "remove", "unsubscribe", "stop",
    "don't contact", "already have", "passing", "passed", "decline",
    "unfortunately", "not a fit", "not relevant", "wrong person",
    "do not", "never", "waste", "spam", "annoying",
]

_OOO_KEYWORDS = [
    "out of office", "ooo", "on vacation", "away from", "auto-reply",
    "automatic reply", "not available", "limited access", "returning on",
    "back on", "in the office on",
]


def analyze_sentiment_keywords(text: str) -> Tuple[Sentiment, float]:
    """
    Fast keyword-based sentiment analysis. No LLM calls.

    Returns (Sentiment, confidence).
    """
    if not text:
        return Sentiment.NEUTRAL, 0.5

    lower = text.lower()
    pos_score = sum(1 for kw in _POSITIVE_KEYWORDS if kw in lower)
    neg_score = sum(1 for kw in _NEGATIVE_KEYWORDS if kw in lower)
    ooo_score = sum(1 for kw in _OOO_KEYWORDS if kw in lower)

    # OOO is neutral sentiment (not negative)
    if ooo_score > 0:
        return Sentiment.NEUTRAL, min(0.5 + ooo_score * 0.15, 0.9)

    total = pos_score + neg_score
    if total == 0:
        return Sentiment.NEUTRAL, 0.5

    pos_ratio = pos_score / total
    neg_ratio = neg_score / total

    if pos_ratio > reply_config.sentiment_positive_threshold:
        confidence = min(0.5 + pos_score * 0.1, 0.95)
        return Sentiment.POSITIVE, confidence
    elif neg_ratio > reply_config.sentiment_negative_threshold:
        confidence = min(0.5 + neg_score * 0.1, 0.95)
        return Sentiment.NEGATIVE, confidence
    else:
        return Sentiment.NEUTRAL, 0.5


def is_out_of_office(text: str) -> bool:
    """Check if the reply is an auto-reply / OOO message."""
    lower = text.lower()
    return any(kw in lower for kw in _OOO_KEYWORDS)


def is_unsubscribe(text: str) -> bool:
    """Check if the reply is an unsubscribe request."""
    lower = text.lower()
    return any(kw in lower for kw in ["unsubscribe", "opt out", "remove me", "stop sending"])
