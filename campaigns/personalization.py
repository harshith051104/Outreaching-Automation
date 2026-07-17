"""
Personalization Engine — generates only AI-dependent placeholders.

Consumes ResearchArtifact. Generates: ai_value_prop, specific_thesis, portfolio_fit, cta.
Never generates: investor_name, firm_name, investor_focus, company_update, sender_name.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Optional

from campaigns.artifacts import PersonalizationArtifact, ResearchArtifact

logger = logging.getLogger(__name__)

# Placeholders the AI should NEVER generate (they come from structured data)
_EXCLUDED_KEYS = {
    "investor_name", "investor name", "name", "firm_name", "firm name", "company",
    "investor_focus", "investor focus", "focus", "investor focus area",
    "company_update", "company update", "sender_name", "sender name",
    "sender_email", "sender email", "first_name", "last_name",
    "email", "website", "linkedin", "role", "title",
}

# Alias groups for matching LLM output keys to template placeholders
_ALIAS_GROUPS = [
    {"ai_value_prop", "aivalueprop", "value_prop", "valueprop", "value_proposition",
     "valueproposition", "proposition", "prop", "benefit", "reason", "proposal", "fit"},
    {"specific_thesis", "specificthesis", "thesis", "thesis_point", "thesispoinit"},
    {"portfolio_fit", "portfoliofit", "fit", "portfoliomatch"},
    {"cta", "call_to_action", "calltoaction"},
]
_ALIAS_LOOKUP = {m: g for g in _ALIAS_GROUPS for m in g}


def _alias_match(norm_ph: str, gen_key: str) -> bool:
    if norm_ph == gen_key or gen_key in norm_ph or norm_ph in gen_key:
        return True
    gp = _ALIAS_LOOKUP.get(norm_ph)
    gg = _ALIAS_LOOKUP.get(gen_key)
    return gp is not None and gp == gg


def _normalize_key(k: str) -> str:
    return (
        k.strip().lower()
        .replace("_", "")
        .replace("-", "")
        .replace(" ", "")
        .replace("{", "")
        .replace("}", "")
        .replace("[", "")
        .replace("]", "")
    )


class PersonalizationEngine:
    """Generates AI-dependent placeholder values using LLM."""

    def __init__(self, llm_manager: Any = None):
        self._llm = llm_manager

    async def generate(
        self,
        research: ResearchArtifact,
        unresolved_placeholders: list[str],
    ) -> PersonalizationArtifact:
        """Generate AI values for unresolved placeholders that require personalization."""
        # Filter to only AI-source placeholders
        ai_placeholders = [p for p in unresolved_placeholders if self._needs_ai(p)]
        if not ai_placeholders:
            return PersonalizationArtifact()

        if not self._llm:
            logger.warning("PersonalizationEngine: No LLM manager available, returning empty")
            return PersonalizationArtifact()

        system_msg = self._build_system_prompt(research, ai_placeholders)
        allowed_keys = list(ai_placeholders)

        try:
            result = await self._llm.generate_completion(
                task_type="email_personalization",
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": f"Generate the JSON object. Only generate keys: {allowed_keys}"},
                ],
                user_id=research.source_data.get("lead", {}).get("user_id", "system"),
                temperature=0.7,
            )
            content = result.get("content", "{}")
            return self._parse_response(content, ai_placeholders)
        except Exception as exc:
            logger.exception("PersonalizationEngine: LLM generation failed: %s", exc)
            raise RuntimeError(f"AI personalization failed: {exc}") from exc

    def _needs_ai(self, placeholder: str) -> bool:
        """Check if a placeholder requires AI generation."""
        norm = placeholder.lower().replace(" ", "_").replace("-", "_")
        # Exclude known non-AI placeholders
        if norm in _EXCLUDED_KEYS or placeholder in _EXCLUDED_KEYS:
            return False
        # Include if it looks like an AI placeholder
        ai_keywords = ["ai_", "value_prop", "thesis", "portfolio", "cta", "personalized"]
        return any(kw in norm for kw in ai_keywords)

    def _build_system_prompt(self, research: ResearchArtifact, placeholders: list[str]) -> str:
        focus_all = ", ".join(research.investor_focus_items) if research.investor_focus_items else "Not specified"
        focus_primary = research.investor_focus or "Not specified"

        prompt_parts = []
        for ph in placeholders:
            prompt_parts.append(
                f"- [{ph}]: Generate a contextually appropriate value for a cold investor outreach email "
                f"for ElectraWireless (wireless power infrastructure startup, $5M seed round)."
            )

        focus_instruction = ""
        if research.investor_focus_items:
            focus_list = "\n".join(f"  {i+1}. {fi}" for i, fi in enumerate(research.investor_focus_items))
            focus_instruction = f"""
STRICT RULES FOR focus placeholders:
- Select from this exact list:
{focus_list}
- Do NOT invent or paraphrase. Copy exact text.
- Pick the ONE item most relevant to: wireless power, energy infrastructure, IoT, hardware, AI, automation, B2B, deep tech."""

        return f"""You are filling in placeholder values in an email template for investor outreach.

IMPORTANT: You are NOT writing an email. You are ONLY generating values for specific placeholder tokens.
The email template is already written — do not change any other part of it.

LEAD CONTEXT:
- Investor Name: {research.investor_name}
- Company/Firm: {research.firm_name}
- Firm Description: {research.firm_description or "Not available"}
- Primary Investment Focus: {focus_primary}
- ALL Investment Focus Areas: {focus_all}
- Email: {research.lead_email}

SENDER CONTEXT (ElectraWireless):
- Product: Wireless power infrastructure (5W-30kW range)
- Markets: Smart Kitchens → Industrial → EV charging
- AI Control Layer: Elly (SaaS revenue stream)
- Raising: $5M seed round{focus_instruction}

Generate ONLY the placeholder values as a JSON object.
- Keys = EXACT placeholder text (without brackets or braces)
- Values = the replacement text (1-2 sentences max, specific and credible)

PLACEHOLDERS TO FILL:
{chr(10).join(prompt_parts)}"""

    def _parse_response(self, content: str, requested: list[str]) -> PersonalizationArtifact:
        """Parse LLM JSON response into PersonalizationArtifact."""
        artifact = PersonalizationArtifact()

        json_match = re.search(r"\{.*?\}", content, re.DOTALL)
        if not json_match:
            return artifact

        try:
            generated = json.loads(json_match.group())
        except json.JSONDecodeError:
            return artifact

        # Normalize and map to artifact fields
        norm_generated = {_normalize_key(k): str(v) for k, v in generated.items() if v}

        # Try direct match first, then alias match
        for field_name in ["ai_value_prop", "specific_thesis", "portfolio_fit", "cta"]:
            norm_field = _normalize_key(field_name)
            matched_val = norm_generated.get(norm_field, "")
            if not matched_val:
                for gk, gv in norm_generated.items():
                    if _alias_match(norm_field, gk):
                        matched_val = gv
                        break
            setattr(artifact, field_name, matched_val)

        # Store remaining as custom fields
        mapped_keys = set()
        for field_name in ["ai_value_prop", "specific_thesis", "portfolio_fit", "cta"]:
            norm_field = _normalize_key(field_name)
            for gk in list(norm_generated.keys()):
                if _alias_match(norm_field, gk):
                    mapped_keys.add(gk)
                    break
            mapped_keys.add(norm_field)

        for gk, gv in norm_generated.items():
            if gk not in mapped_keys and gk not in {k.lower().replace(" ", "") for k in _EXCLUDED_KEYS}:
                artifact.custom_ai_fields[gk] = gv

        return artifact
