"""
Reply subsystem configuration.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ReplyConfig:
    """Configuration for the reply analysis subsystem."""
    # Intent classification
    min_confidence_threshold: float = 0.5
    llm_temperature: float = 0.3
    llm_max_tokens: int = 1024

    # Sentiment
    sentiment_positive_threshold: float = 0.6
    sentiment_negative_threshold: float = 0.6

    # Decision engine
    default_delay_days: int = 14
    ooo_delay_days: int = 7
    timing_not_right_delay_days: int = 30
    follow_up_later_delay_days: int = 14

    # Lead scoring
    lead_score_interested_delta: float = 15.0
    lead_score_meeting_delta: float = 30.0
    lead_score_not_interested_delta: float = -40.0
    lead_score_followup_delta: float = 0.0
    lead_score_neutral_delta: float = 5.0

    # Duplicate detection
    dedup_window_hours: int = 24

    # Logging
    log_raw_body: bool = False  # Never log email bodies in production


reply_config = ReplyConfig()
