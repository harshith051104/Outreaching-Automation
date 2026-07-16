"""
Placeholder Engine — registry-based resolver for template placeholders.

Each placeholder defines: source, type, required, validator, fallback.
Never uses manual .replace(...) chains.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Callable, Dict, List, Optional

from campaigns.artifacts import ResearchArtifact, PersonalizationArtifact
from campaigns.models import DEFAULT_PLACEHOLDERS, PlaceholderDef, PlaceholderSource

logger = logging.getLogger(__name__)


class PlaceholderEngine:
    """Registry-based placeholder resolver. Resolves placeholders from structured data sources."""

    def __init__(self, extra_placeholders: Optional[list[PlaceholderDef]] = None):
        self._registry: Dict[str, PlaceholderDef] = {}
        for p in DEFAULT_PLACEHOLDERS:
            self._registry[p.name] = p
        for p in (extra_placeholders or []):
            self._registry[p.name] = p

    def resolve_all(
        self,
        text: str,
        research: ResearchArtifact,
        personalization: Optional[PersonalizationArtifact] = None,
    ) -> tuple[str, Dict[str, str]]:
        """Resolve all placeholders in text. Returns (resolved_text, applied_map)."""
        if not text:
            return text, {}

        # Normalize non-breaking spaces and standard whitespace
        text = text.replace("\xa0", " ").replace("&nbsp;", " ")

        applied: Dict[str, str] = {}

        # Build value map from research + personalization
        value_map = self._build_value_map(research, personalization)

        # Resolve {{placeholder}} and [placeholder] patterns
        def replace_double(m):
            key = m.group(1).strip()
            # Normalize internal placeholder whitespace
            key = key.replace("\xa0", " ").replace("&nbsp;", " ")
            key_lower = key.lower().replace(" ", "_").replace("-", "_")
            val = value_map.get(key_lower, value_map.get(key, None))
            if val is not None:
                applied[key] = val
                return val
            return m.group(0)

        def replace_single(m):
            key = m.group(1).strip()
            # Normalize internal placeholder whitespace
            key = key.replace("\xa0", " ").replace("&nbsp;", " ")
            key_lower = key.lower().replace(" ", "_").replace("-", "_")
            val = value_map.get(key_lower, value_map.get(key, None))
            if val is not None:
                applied[key] = val
                return val
            return m.group(0)

        result = re.sub(r"\{\{([^}]+)\}\}", replace_double, text)
        result = re.sub(r"\[([^\]]+)\]", replace_single, result)

        # Resolve custom fields from lead data
        result = self._resolve_custom_fields(result, research.custom_fields, applied)

        return result, applied

    def get_unresolved(self, text: str) -> list[str]:
        """Extract remaining {{placeholder}} and [placeholder] patterns."""
        double = re.findall(r"\{\{([^}]+)\}\}", text)
        bracket = re.findall(r"\[([^\]]+)\]", text)
        return double + bracket

    def validate_required(self, text: str) -> list[str]:
        """Return list of required placeholders that are still unresolved."""
        unresolved = self.get_unresolved(text)
        required = [p.name for p in self._registry.values() if p.required]
        return [u for u in unresolved if u.lower().replace(" ", "_") in required]

    def get_definition(self, name: str) -> Optional[PlaceholderDef]:
        return self._registry.get(name)

    def _build_value_map(
        self,
        research: ResearchArtifact,
        personalization: Optional[PersonalizationArtifact] = None,
    ) -> Dict[str, str]:
        """Build normalized key -> value map from all sources."""
        m: Dict[str, str] = {}

        # Spreadsheet data (from research)
        _set_if(m, "investor_name", research.investor_name)
        _set_if(m, "investor name", research.investor_name)
        _set_if(m, "name", research.investor_name)
        _set_if(m, "first_name", research.first_name)
        _set_if(m, "last_name", research.last_name)
        _set_if(m, "firm_name", research.firm_name)
        _set_if(m, "firm name", research.firm_name)
        _set_if(m, "company", research.firm_name)
        _set_if(m, "investor_focus", research.investor_focus)
        _set_if(m, "investor focus", research.investor_focus)
        _set_if(m, "investment_focus", research.investor_focus)
        _set_if(m, "investment focus", research.investor_focus)
        _set_if(m, "focus", research.investor_focus)

        # Focus area variants
        if research.investor_focus_items:
            _set_if(m, "investor focus area", self._pick_best(research.investor_focus_items))
            _set_if(m, "investor focus 1", research.investor_focus_items[0])
            if len(research.investor_focus_items) > 1:
                _set_if(m, "investor focus 2", research.investor_focus_items[1])

        _set_if(m, "role", research.lead_title)
        _set_if(m, "title", research.lead_title)
        _set_if(m, "job_title", research.lead_title)
        _set_if(m, "job title", research.lead_title)
        _set_if(m, "website", research.lead_website)
        _set_if(m, "email", research.lead_email)
        _set_if(m, "linkedin", research.lead_linkedin)
        _set_if(m, "linkedin_url", research.lead_linkedin)
        _set_if(m, "linkedin url", research.lead_linkedin)
        _set_if(m, "notes", research.lead_notes)

        # Sender data
        _set_if(m, "sender_name", research.sender_name)
        _set_if(m, "sender_email", research.sender_email)
        _set_if(m, "sender_title", research.sender_title)
        _set_if(m, "sender title", research.sender_title)

        # Bracket-style placeholders
        _set_if(m, "your name", research.sender_name)
        _set_if(m, "sender name", research.sender_name)
        _set_if(m, "your email", research.sender_email)
        _set_if(m, "sender email", research.sender_email)
        _set_if(m, "your title", research.sender_title)
        _set_if(m, "investor name", research.investor_name)
        _set_if(m, "investors name", research.investor_name)
        _set_if(m, "firm name", research.firm_name)

        # Campaign data
        _set_if(m, "company_update", research.company_update)
        _set_if(m, "company update", research.company_update)
        _set_if(m, "campaign_name", research.campaign_name)
        _set_if(m, "campaign name", research.campaign_name)

        # AI-generated data (only if personalization provided)
        if personalization:
            _set_if(m, "ai_value_prop", personalization.ai_value_prop)
            _set_if(m, "ai value prop", personalization.ai_value_prop)
            _set_if(m, "value_proposition", personalization.ai_value_prop)
            _set_if(m, "value_prop", personalization.ai_value_prop)
            _set_if(m, "specific_thesis", personalization.specific_thesis)
            _set_if(m, "specific thesis", personalization.specific_thesis)
            _set_if(m, "portfolio_fit", personalization.portfolio_fit)
            _set_if(m, "portfolio fit", personalization.portfolio_fit)
            _set_if(m, "cta", personalization.cta)
            for k, v in personalization.custom_ai_fields.items():
                _set_if(m, k.lower().replace(" ", "_"), v)

        return m

    def _resolve_custom_fields(self, text: str, custom_fields: Dict[str, Any], applied: Dict[str, str]) -> str:
        if not custom_fields:
            return text
        result = text
        for k, v in custom_fields.items():
            val_str = str(v) if v else ""
            if not val_str:
                continue
            key_raw = k.strip()
            key_underscore = key_raw.lower().replace(" ", "_")
            key_spaced = key_raw.lower().replace("_", " ")
            key_flat = key_raw.lower().replace(" ", "").replace("_", "")
            for pk in {key_raw, key_raw.lower(), key_underscore, key_spaced, key_flat}:
                if not pk:
                    continue
                result = re.sub(r"\{\{\s*" + re.escape(pk) + r"\s*\}\}", val_str, result, flags=re.IGNORECASE)
                result = re.sub(r"\[\s*" + re.escape(pk) + r"\s*\]", val_str, result, flags=re.IGNORECASE)
                if result != text:
                    applied[key_raw] = val_str
        return result

    def _pick_best(self, items: list[str]) -> str:
        for fi in items:
            if any(kw in fi.lower() for kw in [
                "wireless", "iot", "energy", "power", "hardware", "ai",
                "infrastructure", "semiconductor", "robotics", "smart",
            ]):
                return fi
        return items[0] if items else ""


def _set_if(d: Dict[str, str], key: str, value: str) -> None:
    """Set a value in the map. Allows empty strings to resolve placeholders to empty."""
    d[key.lower().replace(" ", "_")] = str(value) if value else ""
