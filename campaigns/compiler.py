"""
Template Compiler — compiles templates into EmailArtifact.

Supports {{ }} and [ ] placeholders. Future-ready for conditionals and loops.
Does not perform ad-hoc string replacement.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional

from campaigns.artifacts import EmailArtifact, ResearchArtifact, PersonalizationArtifact
from campaigns.placeholder_engine import PlaceholderEngine

logger = logging.getLogger(__name__)


class TemplateCompiler:
    """Compiles email templates with resolved placeholders into EmailArtifact."""

    def __init__(self, placeholder_engine: PlaceholderEngine):
        self._placeholder_engine = placeholder_engine

    def compile(
        self,
        subject_template: str,
        body_template: str,
        research: ResearchArtifact,
        personalization: Optional[PersonalizationArtifact] = None,
    ) -> EmailArtifact:
        """Compile templates into a final EmailArtifact."""
        # Resolve placeholders in subject and body
        resolved_subject, subject_placeholders = self._placeholder_engine.resolve_all(
            subject_template, research, personalization
        )
        resolved_body, body_placeholders = self._placeholder_engine.resolve_all(
            body_template, research, personalization
        )

        # Merge applied placeholders
        all_placeholders = {**subject_placeholders, **body_placeholders}

        return EmailArtifact(
            subject=resolved_subject,
            body=resolved_body,
            placeholders=all_placeholders,
            lead_id=research.lead_id,
            campaign_id=research.campaign_id,
        )

    def convert_to_html(self, text: str) -> str:
        """Convert plain text to HTML with paragraph and formatting handling."""
        if not text:
            return ""

        text = text.replace("\r\n", "\n").replace("\r", "\n")

        has_html = "<p>" in text.lower() or "<br" in text.lower() or "<div>" in text.lower()
        if not has_html:
            paragraphs = text.split("\n\n")
            formatted = []
            for p in paragraphs:
                if p.strip():
                    formatted_p = p.replace("\n", "<br />")
                    formatted.append(f"<p>{formatted_p}</p>")
            text = "\n".join(formatted)

        text = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", text)
        text = re.sub(r"\*(.*?)\*", r"<em>\1</em>", text)

        return text
