"""
Personalization Scorer — scores email quality based on personalization depth.
"""

from __future__ import annotations

from typing import Optional

from campaigns.artifacts import ResearchArtifact, PersonalizationArtifact


class PersonalizationScorer:
    """Scores emails based on how well they are personalized."""

    def __init__(self, weights: Optional[dict] = None):
        self._weights = weights or {
            "investor_name": 20,
            "firm_name": 15,
            "investor_focus": 20,
            "ai_value_prop": 25,
            "specific_thesis": 10,
            "portfolio_fit": 10,
        }

    def score(
        self,
        research: ResearchArtifact,
        personalization: Optional[PersonalizationArtifact] = None,
    ) -> int:
        """Calculate personalization score (0-100)."""
        total = 0

        if research.investor_name:
            total += self._weights["investor_name"]
        if research.firm_name:
            total += self._weights["firm_name"]
        if research.investor_focus:
            total += self._weights["investor_focus"]

        if personalization:
            if personalization.ai_value_prop:
                total += self._weights["ai_value_prop"]
            if personalization.specific_thesis:
                total += self._weights["specific_thesis"]
            if personalization.portfolio_fit:
                total += self._weights["portfolio_fit"]

        return min(total, 100)
