"""
Validation Engine — validates emails before sending.

Checks: unresolved placeholders, required fields, length, hallucination, personalization score.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from campaigns.artifacts import EmailArtifact, ResearchArtifact
from campaigns.placeholder_engine import PlaceholderEngine

logger = logging.getLogger(__name__)


class ValidationEngine:
    """Validates email artifacts before sending."""

    def __init__(
        self,
        placeholder_engine: PlaceholderEngine,
        min_score: int = 60,
        max_subject_length: int = 200,
        max_body_length: int = 10000,
        max_paragraphs: int = 20,
    ):
        self._placeholder_engine = placeholder_engine
        self._min_score = min_score
        self._max_subject_length = max_subject_length
        self._max_body_length = max_body_length
        self._max_paragraphs = max_paragraphs

    def validate(
        self,
        subject: str,
        body: str,
        research: Optional[ResearchArtifact] = None,
        score: int = 0,
    ) -> Dict[str, Any]:
        """Run all validation checks. Returns validation report."""
        issues: List[str] = []
        warnings: List[str] = []

        # 1. Placeholder validation — no unresolved {{ }} or [[ ]]
        unresolved = self._placeholder_engine.get_unresolved(subject + " " + body)
        if unresolved:
            issues.append(f"Unresolved placeholders: {unresolved}")

        # 2. Required fields
        required_missing = self._placeholder_engine.validate_required(subject + " " + body)
        if required_missing:
            issues.append(f"Required placeholders missing: {required_missing}")

        # 3. Length validation
        if len(subject) > self._max_subject_length:
            issues.append(f"Subject too long: {len(subject)} > {self._max_subject_length}")
        if len(body) > self._max_body_length:
            issues.append(f"Body too long: {len(body)} > {self._max_body_length}")

        paragraphs = [p for p in body.split("\n\n") if p.strip()]
        if len(paragraphs) > self._max_paragraphs:
            warnings.append(f"Too many paragraphs: {len(paragraphs)}")

        if not subject.strip():
            issues.append("Subject is empty")
        if not body.strip():
            issues.append("Body is empty")

        # 4. Hallucination validation — check AI output contradicts campaign data
        if research:
            hallucination = self._check_hallucination(body, research)
            if hallucination:
                issues.append(f"Hallucination detected: {hallucination}")

        # 5. Personalization score
        if score < self._min_score:
            issues.append(f"Personalization score {score} below minimum {self._min_score}")

        passed = len(issues) == 0
        return {
            "passed": passed,
            "issues": issues,
            "warnings": warnings,
            "score": score,
            "unresolved": unresolved,
        }

    def _check_hallucination(self, body: str, research: ResearchArtifact) -> Optional[str]:
        """Check if AI output contradicts known campaign data."""
        body_lower = body.lower()

        # Check company update consistency
        if research.company_update:
            # If body mentions progress but contradicts the approved update
            update_keywords = ["prototype", "validation", "expanded", "platform"]
            body_mentions_progress = any(kw in body_lower for kw in update_keywords)
            approved_mentions_progress = any(
                kw in research.company_update.lower() for kw in update_keywords
            )
            if body_mentions_progress and not approved_mentions_progress:
                return "Body mentions progress not in approved company update"

        # Check sender name consistency
        if research.sender_name and research.sender_name.lower() in body_lower:
            pass  # Sender name in body is fine

        # Check investor name consistency
        if research.investor_name:
            # If body uses a different name than the research data
            name_pattern = re.compile(r"dear\s+(\w+)", re.IGNORECASE)
            match = name_pattern.search(body)
            if match:
                greeting_name = match.group(1)
                if greeting_name.lower() != research.investor_name.split()[0].lower():
                    return f"Greeting uses '{greeting_name}' but investor is '{research.investor_name}'"

        return None
