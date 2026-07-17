"""
Retry manager with configurable backoff policies.
"""

from __future__ import annotations

import random
from datetime import datetime, timezone, timedelta
from typing import Optional

from email_delivery.models import RetryPolicy


class RetryManager:
    """Compute retry delays and next-retry timestamps."""

    def __init__(
        self,
        policy: RetryPolicy = RetryPolicy.EXPONENTIAL,
        base_delay: float = 5.0,
        max_delay: float = 300.0,
        max_attempts: int = 3,
    ):
        self.policy = policy
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.max_attempts = max_attempts

    def should_retry(self, attempt: int) -> bool:
        if self.policy == RetryPolicy.NONE:
            return False
        return attempt < self.max_attempts

    def compute_delay(self, attempt: int) -> float:
        if self.policy == RetryPolicy.NONE:
            return 0.0
        if self.policy == RetryPolicy.FIXED:
            return min(self.base_delay, self.max_delay)
        if self.policy == RetryPolicy.EXPONENTIAL:
            delay = self.base_delay * (2 ** attempt)
            return min(delay, self.max_delay)
        if self.policy == RetryPolicy.EXPONENTIAL_JITTER:
            delay = self.base_delay * (2 ** attempt)
            delay = min(delay, self.max_delay)
            jitter = delay * 0.25 * random.random()
            return delay + jitter
        return 0.0

    def next_retry_at(self, attempt: int) -> Optional[datetime]:
        if not self.should_retry(attempt):
            return None
        delay = self.compute_delay(attempt)
        if delay <= 0:
            return None
        return datetime.now(timezone.utc) + timedelta(seconds=delay)
