"""
Core models for placeholder definitions, prompt versioning, and cache entries.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, Optional


class PlaceholderSource(str, Enum):
    SPREADSHEET = "spreadsheet"
    CAMPAIGN = "campaign"
    AI = "ai"
    STATIC = "static"
    SENDER = "sender"


@dataclass
class PlaceholderDef:
    """Registry entry for a single placeholder."""
    name: str
    source: PlaceholderSource
    required: bool = True
    validator: Optional[Callable[[str], bool]] = None
    fallback: str = ""
    description: str = ""

    def validate(self, value: str) -> bool:
        if self.validator:
            return self.validator(value)
        return bool(value.strip()) if self.required else True


@dataclass
class PromptVersion:
    """Tracks prompt versioning for audit trail."""
    prompt_id: str
    version: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    template: str = ""
    description: str = ""


@dataclass
class CacheEntry:
    """AI cache entry keyed by campaign_id + investor_focus + template_version."""
    cache_key: str
    values: Dict[str, str] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    expires_at: Optional[str] = None
    hit_count: int = 0


# ── Default placeholder registry ──────────────────────────────────────────

DEFAULT_PLACEHOLDERS: list[PlaceholderDef] = [
    PlaceholderDef(
        name="investor_name",
        source=PlaceholderSource.SPREADSHEET,
        required=True,
        description="Investor's full name from lead data",
    ),
    PlaceholderDef(
        name="firm_name",
        source=PlaceholderSource.SPREADSHEET,
        required=True,
        description="Investor's firm/company from lead data",
    ),
    PlaceholderDef(
        name="investor_focus",
        source=PlaceholderSource.SPREADSHEET,
        required=True,
        description="Investor's selected focus area from spreadsheet column",
    ),
    PlaceholderDef(
        name="company_update",
        source=PlaceholderSource.CAMPAIGN,
        required=True,
        description="Campaign-wide company update (static per campaign)",
    ),
    PlaceholderDef(
        name="ai_value_prop",
        source=PlaceholderSource.AI,
        required=True,
        description="AI-generated value proposition",
    ),
    PlaceholderDef(
        name="specific_thesis",
        source=PlaceholderSource.AI,
        required=False,
        description="AI-generated specific thesis point",
    ),
    PlaceholderDef(
        name="portfolio_fit",
        source=PlaceholderSource.AI,
        required=False,
        description="AI-generated portfolio fit explanation",
    ),
    PlaceholderDef(
        name="sender_name",
        source=PlaceholderSource.SENDER,
        required=True,
        description="Email sender's name",
    ),
    PlaceholderDef(
        name="sender_email",
        source=PlaceholderSource.SENDER,
        required=True,
        description="Email sender's email address",
    ),
    PlaceholderDef(
        name="sender_title",
        source=PlaceholderSource.SENDER,
        required=False,
        fallback="Founder & CEO",
        description="Email sender's title",
    ),
    PlaceholderDef(
        name="first_name",
        source=PlaceholderSource.SPREADSHEET,
        required=True,
        description="Investor's first name",
    ),
    PlaceholderDef(
        name="last_name",
        source=PlaceholderSource.SPREADSHEET,
        required=False,
        description="Investor's last name",
    ),
    PlaceholderDef(
        name="company",
        source=PlaceholderSource.SPREADSHEET,
        required=False,
        description="Investor's company (alias for firm_name)",
    ),
    PlaceholderDef(
        name="focus",
        source=PlaceholderSource.SPREADSHEET,
        required=False,
        description="Investor focus (alias for investor_focus)",
    ),
    PlaceholderDef(
        name="role",
        source=PlaceholderSource.SPREADSHEET,
        required=False,
        description="Investor's role/title",
    ),
    PlaceholderDef(
        name="title",
        source=PlaceholderSource.SPREADSHEET,
        required=False,
        description="Investor's title (alias for role)",
    ),
    PlaceholderDef(
        name="website",
        source=PlaceholderSource.SPREADSHEET,
        required=False,
        description="Investor's website",
    ),
    PlaceholderDef(
        name="email",
        source=PlaceholderSource.SPREADSHEET,
        required=False,
        description="Investor's email address",
    ),
    PlaceholderDef(
        name="linkedin",
        source=PlaceholderSource.SPREADSHEET,
        required=False,
        description="Investor's LinkedIn URL",
    ),
]
