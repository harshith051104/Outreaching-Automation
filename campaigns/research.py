"""
Research Engine — collects structured data from all sources for a single lead.

Returns a ResearchArtifact containing only structured information.
Never generates email content.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from campaigns.artifacts import ResearchArtifact

logger = logging.getLogger(__name__)


class ResearchEngine:
    """Collects structured research data for a lead from lead CSV, campaign config, and MongoDB."""

    ELECTRA_KEYWORDS = [
        "wireless", "iot", "internet of things", "energy", "power", "hardware",
        "ai", "artificial intelligence", "automation", "b2b", "saas", "infrastructure",
        "deep tech", "deeptech", "semiconductor", "robotics", "smart", "manufacturing",
        "industrial", "finance", "fintech", "climate", "clean", "electrification",
        "mobility", "ev", "logistics", "developer", "cloud", "cybersecurity",
    ]

    async def collect(
        self,
        lead: Dict[str, Any],
        campaign: Dict[str, Any],
        user: Optional[Dict[str, Any]] = None,
        gmail_account: Optional[Dict[str, Any]] = None,
    ) -> ResearchArtifact:
        """Build a ResearchArtifact from lead, campaign, and user data."""
        lead_name = self._build_lead_name(lead)
        focus_raw = lead.get("focus", "") or ""
        focus_items = [f.strip() for f in focus_raw.split(",") if f.strip()]
        best_focus = self._pick_best_focus(focus_items)

        sender_name = ""
        sender_email = ""
        if gmail_account:
            sender_name = gmail_account.get("name", "")
            sender_email = gmail_account.get("email", "")
        if not sender_name and user:
            sender_name = user.get("name", "")
        if not sender_email and user:
            sender_email = user.get("email", "")

        company_update = campaign.get("company_update", "") or ""

        return ResearchArtifact(
            lead_id=lead.get("id", ""),
            campaign_id=campaign.get("id", ""),
            investor_name=lead_name,
            first_name=lead.get("first_name", "").strip(),
            last_name=lead.get("last_name", "").strip(),
            firm_name=lead.get("company", ""),
            investor_focus=best_focus or (focus_items[0] if focus_items else ""),
            investor_focus_items=focus_items,
            firm_description=(lead.get("custom_fields") or {}).get("firm_description", ""),
            lead_email=lead.get("email", ""),
            lead_title=lead.get("title") or lead.get("role") or "",
            lead_website=lead.get("website", ""),
            lead_linkedin=lead.get("linkedin", ""),
            lead_notes=lead.get("notes", ""),
            custom_fields=lead.get("custom_fields") or {},
            company_update=company_update,
            sender_name=sender_name,
            sender_email=sender_email,
            sender_title="Founder & CEO",
            campaign_name=campaign.get("name", ""),
            campaign_description=campaign.get("description", ""),
            campaign_settings=campaign.get("settings") or {},
            source_data={
                "lead": lead,
                "campaign": campaign,
                "user": user or {},
                "gmail_account": gmail_account or {},
            },
        )

    def _build_lead_name(self, lead: Dict[str, Any]) -> str:
        first = lead.get("first_name", "").strip()
        last = lead.get("last_name", "").strip()
        if last and first.lower().endswith(last.lower()):
            last = ""
        if first and last:
            return f"{first} {last}"
        return first or lead.get("name", "") or lead.get("email", "")

    def _pick_best_focus(self, focus_items: list[str]) -> str:
        if not focus_items:
            return ""
        for fi in focus_items:
            if any(kw in fi.lower() for kw in self.ELECTRA_KEYWORDS):
                return fi
        return focus_items[0]
