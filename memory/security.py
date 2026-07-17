"""
Memory security — collection-level access control.

Enforces user, workspace, and campaign isolation.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set

from memory.config import memory_config

logger = logging.getLogger(__name__)

# Permission definitions (mirrors memory_registry.yaml)
COLLECTION_PERMISSIONS: Dict[str, Dict[str, str]] = {
    "leads": {"read": {"rag_agent", "personalization_agent", "email_writer", "followup_agent", "analytics_agent"}, "write": {"lead_discovery", "signal_intelligence", "rag_agent"}},
    "campaigns": {"read": {"research_agent", "personalization_agent", "email_writer", "analytics_agent", "rag_agent"}, "write": {"campaign_strategist", "analytics_agent", "rag_agent"}},
    "emails": {"read": {"rag_agent", "followup_agent"}, "write": {"email_writer", "rag_agent"}},
    "replies": {"read": {"followup_agent", "analytics_agent", "rag_agent"}, "write": {"reply_monitor_agent", "rag_agent"}},
    "signals": {"read": {"opportunity_agent", "personalization_agent", "rag_agent"}, "write": {"signal_intelligence"}},
    "knowledge": {"read": {"rag_agent"}, "write": {"rag_agent"}},
    "documents": {"read": {"rag_agent"}, "write": {"rag_agent"}},
    "investors": {"read": {"rag_agent", "research_agent", "personalization_agent"}, "write": {"rag_agent"}},
    "companies": {"read": {"rag_agent", "research_agent"}, "write": {"rag_agent"}},
    "templates": {"read": {"email_writer", "rag_agent"}, "write": {"email_writer", "rag_agent"}},
    "crm": {"read": {"rag_agent"}, "write": {"rag_agent"}},
    "notes": {"read": {"rag_agent"}, "write": {"rag_agent"}},
    "company_research": {"read": {"rag_agent", "research_agent"}, "write": {"rag_agent"}},
    "kb_documents": {"read": {"rag_agent"}, "write": {"rag_agent"}},
    "linkedin_outreach": {"read": {"rag_agent"}, "write": {"rag_agent"}},
}


class AccessContext:
    """Represents the security context for a memory operation."""

    def __init__(
        self,
        agent_id: str = "",
        user_id: str = "",
        workspace_id: str = "",
        campaign_ids: Optional[Set[str]] = None,
    ):
        self.agent_id = agent_id
        self.user_id = user_id
        self.workspace_id = workspace_id
        self.campaign_ids = campaign_ids or set()


def can_read(collection: str, context: AccessContext) -> bool:
    """Check if the agent can read from a collection."""
    if not memory_config.security.enforce_user_isolation:
        return True

    perms = COLLECTION_PERMISSIONS.get(collection, {})
    read_agents = perms.get("read", set())
    if not read_agents:
        return True  # no restriction
    return context.agent_id in read_agents


def can_write(collection: str, context: AccessContext) -> bool:
    """Check if the agent can write to a collection."""
    if not memory_config.security.enforce_user_isolation:
        return True

    perms = COLLECTION_PERMISSIONS.get(collection, {})
    write_agents = perms.get("write", set())
    if not write_agents:
        return True  # no restriction
    return context.agent_id in write_agents


def filter_by_user(records: List[Dict[str, Any]], user_id: str) -> List[Dict[str, Any]]:
    """Filter records to only those belonging to the user."""
    if not memory_config.security.enforce_user_isolation or not user_id:
        return records
    return [r for r in records if r.get("user_id", "") == user_id or r.get("metadata", {}).get("user_id", "") == user_id]


def filter_by_campaign(records: List[Dict[str, Any]], campaign_ids: Set[str]) -> List[Dict[str, Any]]:
    """Filter records to only those in the allowed campaigns."""
    if not memory_config.security.enforce_campaign_isolation or not campaign_ids:
        return records
    return [
        r for r in records
        if r.get("campaign_id", "") in campaign_ids
        or r.get("metadata", {}).get("campaign_id", "") in campaign_ids
        or not r.get("campaign_id")
    ]


def apply_security_filter(
    records: List[Dict[str, Any]],
    context: AccessContext,
) -> List[Dict[str, Any]]:
    """Apply all security filters to a set of records."""
    result = records
    if memory_config.security.enforce_user_isolation and context.user_id:
        result = filter_by_user(result, context.user_id)
    if memory_config.security.enforce_campaign_isolation and context.campaign_ids:
        result = filter_by_campaign(result, context.campaign_ids)
    return result
