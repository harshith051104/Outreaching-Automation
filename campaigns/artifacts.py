"""
Data artifacts flowing through the email compilation pipeline.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional


@dataclass
class ResearchArtifact:
    """Structured data collected from all sources for a single lead."""
    lead_id: str = ""
    campaign_id: str = ""
    investor_name: str = ""
    first_name: str = ""
    last_name: str = ""
    firm_name: str = ""
    investor_focus: str = ""
    investor_focus_items: list[str] = field(default_factory=list)
    firm_description: str = ""
    lead_email: str = ""
    lead_title: str = ""
    lead_website: str = ""
    lead_linkedin: str = ""
    lead_notes: str = ""
    custom_fields: Dict[str, Any] = field(default_factory=dict)
    company_update: str = ""
    sender_name: str = ""
    sender_email: str = ""
    sender_title: str = "Founder & CEO"
    campaign_name: str = ""
    campaign_description: str = ""
    campaign_settings: Dict[str, Any] = field(default_factory=dict)
    source_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "lead_id": self.lead_id,
            "campaign_id": self.campaign_id,
            "investor_name": self.investor_name,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "firm_name": self.firm_name,
            "investor_focus": self.investor_focus,
            "investor_focus_items": self.investor_focus_items,
            "firm_description": self.firm_description,
            "lead_email": self.lead_email,
            "lead_title": self.lead_title,
            "lead_website": self.lead_website,
            "lead_linkedin": self.lead_linkedin,
            "lead_notes": self.lead_notes,
            "custom_fields": self.custom_fields,
            "company_update": self.company_update,
            "sender_name": self.sender_name,
            "sender_email": self.sender_email,
            "sender_title": self.sender_title,
            "campaign_name": self.campaign_name,
            "campaign_description": self.campaign_description,
            "campaign_settings": self.campaign_settings,
            "source_data": self.source_data,
        }


@dataclass
class PersonalizationArtifact:
    """AI-generated values for placeholders that require personalization."""
    ai_value_prop: str = ""
    specific_thesis: str = ""
    portfolio_fit: str = ""
    cta: str = ""
    custom_ai_fields: Dict[str, str] = field(default_factory=dict)
    prompt_id: str = ""
    prompt_version: str = ""
    tokens_used: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ai_value_prop": self.ai_value_prop,
            "specific_thesis": self.specific_thesis,
            "portfolio_fit": self.portfolio_fit,
            "cta": self.cta,
            "custom_ai_fields": self.custom_ai_fields,
            "prompt_id": self.prompt_id,
            "prompt_version": self.prompt_version,
            "tokens_used": self.tokens_used,
        }


@dataclass
class EmailArtifact:
    """Final compiled email ready for sending. The only object passed to the sender."""
    subject: str = ""
    body: str = ""
    placeholders: Dict[str, str] = field(default_factory=dict)
    score: int = 0
    provider: str = ""
    tokens: int = 0
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    validation: Dict[str, Any] = field(default_factory=dict)
    prompt_id: str = ""
    prompt_version: str = ""
    lead_id: str = ""
    campaign_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "subject": self.subject,
            "body": self.body,
            "placeholders": self.placeholders,
            "score": self.score,
            "provider": self.provider,
            "tokens": self.tokens,
            "generated_at": self.generated_at,
            "validation": self.validation,
            "prompt_id": self.prompt_id,
            "prompt_version": self.prompt_version,
            "lead_id": self.lead_id,
            "campaign_id": self.campaign_id,
        }
