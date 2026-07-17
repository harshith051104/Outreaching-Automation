"""
Compilation Pipeline — end-to-end email generation.

Research -> Personalization -> Resolve Placeholders -> Validation -> Compile Template -> Validation -> Score -> Email Artifact
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from campaigns.artifacts import EmailArtifact, ResearchArtifact
from campaigns.cache import AICache
from campaigns.compiler import TemplateCompiler
from campaigns.placeholder_engine import PlaceholderEngine
from campaigns.personalization import PersonalizationEngine
from campaigns.prompt_manager import PromptManager
from campaigns.research import ResearchEngine
from campaigns.scorer import PersonalizationScorer
from campaigns.validator import ValidationEngine

logger = logging.getLogger(__name__)


async def compile_email(
    lead: Dict[str, Any],
    campaign: Dict[str, Any],
    subject_template: str,
    body_template: str,
    user: Optional[Dict[str, Any]] = None,
    gmail_account: Optional[Dict[str, Any]] = None,
    *,
    research_engine: Optional[ResearchEngine] = None,
    personalization_engine: Optional[PersonalizationEngine] = None,
    placeholder_engine: Optional[PlaceholderEngine] = None,
    validator: Optional[ValidationEngine] = None,
    compiler: Optional[TemplateCompiler] = None,
    scorer: Optional[PersonalizationScorer] = None,
    cache: Optional[AICache] = None,
    prompt_manager: Optional[PromptManager] = None,
) -> EmailArtifact:
    """Full compilation pipeline: research -> personalize -> resolve -> validate -> compile -> score."""

    # 1. Research — collect structured data
    research_engine = research_engine or ResearchEngine()
    research = await research_engine.collect(lead, campaign, user, gmail_account)

    # 2. Pre-resolve to find what needs AI
    placeholder_engine = placeholder_engine or PlaceholderEngine()
    pre_subject, _ = placeholder_engine.resolve_all(subject_template, research)
    pre_body, _ = placeholder_engine.resolve_all(body_template, research)
    unresolved = placeholder_engine.get_unresolved(pre_subject + " " + pre_body)

    # 3. Check cache for AI values
    personalization = None
    ai_cache = cache or AICache()
    cached_values = None
    if unresolved and research.investor_focus:
        cached_values = await ai_cache.get(
            research.campaign_id, research.investor_focus
        )

    # 4. Personalization — generate AI values if needed
    if unresolved:
        personalization_engine = personalization_engine or PersonalizationEngine()
        if cached_values:
            # Apply cached values directly
            from campaigns.personalization import PersonalizationArtifact
            personalization = PersonalizationArtifact(
                ai_value_prop=cached_values.get("ai_value_prop", ""),
                specific_thesis=cached_values.get("specific_thesis", ""),
                portfolio_fit=cached_values.get("portfolio_fit", ""),
                cta=cached_values.get("cta", ""),
            )
        else:
            personalization = await personalization_engine.generate(research, unresolved)
            # Cache the generated values
            if personalization and research.investor_focus:
                cache_values = personalization.to_dict()
                await ai_cache.set(
                    research.campaign_id, research.investor_focus,
                    {k: v for k, v in cache_values.items() if v and k not in ("prompt_id", "prompt_version", "tokens_used")}
                )

    # 5. Compile — resolve all placeholders into final artifact
    compiler = compiler or TemplateCompiler(placeholder_engine)
    artifact = compiler.compile(subject_template, body_template, research, personalization)

    # 6. Convert body to HTML
    artifact.body = compiler.convert_to_html(artifact.body)

    # 7. Score — calculate personalization score
    scorer = scorer or PersonalizationScorer()
    artifact.score = scorer.score(research, personalization)

    # 8. Validate — run all validation checks
    validator = validator or ValidationEngine(placeholder_engine)
    validation = validator.validate(
        artifact.subject, artifact.body,
        research=research, score=artifact.score,
    )
    artifact.validation = validation

    # 9. Record prompt version
    pm = prompt_manager or PromptManager()
    prompt = pm.get_current()
    artifact.prompt_id = prompt.prompt_id
    artifact.prompt_version = prompt.version

    # 10. Set provider info
    if personalization:
        artifact.tokens = personalization.tokens_used

    return artifact
