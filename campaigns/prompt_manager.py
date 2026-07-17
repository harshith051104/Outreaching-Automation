"""
Prompt Manager — tracks prompt versions for audit trail.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from campaigns.models import PromptVersion

logger = logging.getLogger(__name__)


class PromptManager:
    """Manages prompt versioning for audit and reproducibility."""

    def __init__(self, db: Any = None):
        self._db = db
        self._current = PromptVersion(
            prompt_id="email_personalization_v1",
            version="1.0.0",
            description="Initial email personalization prompt",
        )

    def get_current(self) -> PromptVersion:
        return self._current

    async def record_usage(self, prompt_id: str, version: str, email_id: str) -> None:
        """Record that a prompt version was used for an email."""
        if not self._db:
            return
        try:
            await self._db.prompt_usage.insert_one({
                "prompt_id": prompt_id,
                "version": version,
                "email_id": email_id,
                "used_at": datetime.now(timezone.utc),
            })
        except Exception as e:
            logger.warning("PromptManager: Failed to record usage: %s", e)
