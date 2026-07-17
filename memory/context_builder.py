"""
Context builder — assembles structured AI context from retrieved memories.

This is the bridge between raw retrieval and downstream AI modules.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from memory.models import ContextPackage, SearchResult
from memory.retrieval_engine import search, ranked_search
from memory.config import memory_config

logger = logging.getLogger(__name__)


def build_context(
    query: str,
    collections: Optional[List[str]] = None,
    current_campaign_id: Optional[str] = None,
    lead_id: Optional[str] = None,
    user_id: Optional[str] = None,
    limit_per_collection: int = 3,
) -> ContextPackage:
    """
    Assemble a ContextPackage from multiple collections.

    Returns a structured dict ready for AI consumption.
    """
    target_collections = collections or [
        "investors", "companies", "campaigns", "emails",
        "replies", "knowledge", "signals",
    ]

    package = ContextPackage(query=query)

    for coll in target_collections:
        filters: Dict[str, Any] = {}
        if lead_id and coll in ("emails", "replies"):
            filters["lead_id"] = lead_id
        if user_id:
            filters["user_id"] = user_id
        if current_campaign_id and coll in ("campaigns", "emails"):
            filters["campaign_id"] = current_campaign_id

        results = ranked_search(
            query=query,
            collection=coll,
            limit=limit_per_collection,
            current_campaign_id=current_campaign_id,
            filters=filters or None,
        )

        _dispatch_results(package, coll, results)

    # Metadata
    package.metadata = {
        "total_items": (
            len(package.recent_emails)
            + len(package.past_replies)
            + len(package.knowledge)
            + len(package.signals)
            + len(package.portfolio)
        ),
        "collections_searched": target_collections,
        "campaign_id": current_campaign_id,
        "lead_id": lead_id,
    }

    return package


def _dispatch_results(
    package: ContextPackage,
    collection: str,
    results: List[SearchResult],
) -> None:
    """Route results to the appropriate context field."""
    items = [r.to_dict() for r in results]

    if collection in ("emails",):
        package.recent_emails.extend(items)
    elif collection in ("replies",):
        package.past_replies.extend(items)
    elif collection in ("knowledge", "documents", "kb_documents"):
        package.knowledge.extend(items)
    elif collection in ("signals",):
        package.signals.extend(items)
    elif collection in ("investors",):
        if items:
            package.investor = items[0]  # primary investor context
            if len(items) > 1:
                package.portfolio.extend(items[1:])
    elif collection in ("companies", "company_research"):
        if items:
            package.company = items[0]
    elif collection in ("campaigns",):
        if items:
            package.campaign = items[0]


def build_investor_context(
    query: str,
    campaign_id: Optional[str] = None,
    lead_id: Optional[str] = None,
) -> ContextPackage:
    """Build context focused on investor + company knowledge."""
    return build_context(
        query=query,
        collections=["investors", "companies", "campaigns", "emails", "replies", "knowledge"],
        current_campaign_id=campaign_id,
        lead_id=lead_id,
    )


def build_campaign_context(
    query: str,
    campaign_id: str,
) -> ContextPackage:
    """Build context focused on a specific campaign."""
    return build_context(
        query=query,
        collections=["campaigns", "emails", "replies", "signals"],
        current_campaign_id=campaign_id,
    )


def context_to_prompt(package: ContextPackage) -> str:
    """Convert a ContextPackage to a prompt-ready string."""
    parts = [f"Query: {package.query}"]

    if package.investor:
        parts.append(f"\nInvestor: {_dict_to_str(package.investor)}")
    if package.company:
        parts.append(f"\nCompany: {_dict_to_str(package.company)}")
    if package.campaign:
        parts.append(f"\nCampaign: {_dict_to_str(package.campaign)}")
    if package.recent_emails:
        parts.append("\nRecent Emails:")
        for e in package.recent_emails[:3]:
            parts.append(f"  - {e.get('text', '')[:200]}")
    if package.past_replies:
        parts.append("\nPast Replies:")
        for r in package.past_replies[:3]:
            parts.append(f"  - {r.get('text', '')[:200]}")
    if package.knowledge:
        parts.append("\nKnowledge:")
        for k in package.knowledge[:3]:
            parts.append(f"  - {k.get('text', '')[:200]}")
    if package.signals:
        parts.append("\nSignals:")
        for s in package.signals[:2]:
            parts.append(f"  - {s.get('text', '')[:200]}")

    return "\n".join(parts)


def _dict_to_str(d: Dict[str, Any]) -> str:
    text = d.get("text", "")
    if text:
        return text[:500]
    return str(d)[:500]
