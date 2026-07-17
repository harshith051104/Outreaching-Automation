"""
Reply summarizer — generates structured summary of reply content.

Uses AI for summarization with action items and priority.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Optional

from reply.models import ReplySummary
from reply.config import reply_config

logger = logging.getLogger(__name__)


def summarize_reply(
    reply_text: str,
    lead_context: Optional[Dict[str, Any]] = None,
    use_llm: bool = True,
) -> ReplySummary:
    """
    Generate a structured summary of a reply.

    Args:
        reply_text: Clean reply text.
        lead_context: Dict with name, company, role.
        use_llm: Whether to use LLM (False = keyword fallback).

    Returns:
        ReplySummary with summary, action_items, priority, key_topics.
    """
    if not reply_text or len(reply_text.strip()) < 10:
        return ReplySummary(
            summary="Empty or very short reply.",
            action_items=["Review reply manually"],
            priority="low",
            key_topics=[],
        )

    if use_llm:
        try:
            return _summarize_llm(reply_text, lead_context)
        except Exception as exc:
            logger.warning("LLM summarization failed: %s", exc)

    return _summarize_keywords(reply_text)


def _summarize_llm(
    reply_text: str,
    lead_context: Optional[Dict[str, Any]] = None,
) -> ReplySummary:
    """LLM-powered summarization."""
    from app.services.llm_manager import LLMManager

    ctx = lead_context or {}
    lead_name = ctx.get("name", "the investor")

    system_prompt = (
        "You are a concise reply summarizer for investor outreach. "
        "Summarize the reply in 1-2 sentences, extract action items, "
        "determine priority (high/medium/low), and list key topics. "
        "Return JSON: {\"summary\": \"...\", \"action_items\": [...], "
        "\"priority\": \"high|medium|low\", \"key_topics\": [...]}"
    )

    user_prompt = f"""Summarize this reply from {lead_name}:

---
{reply_text[:2000]}
---

Return JSON with summary, action_items, priority, key_topics."""

    llm = LLMManager()
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    raw = llm.generate_completion(messages=messages, temperature=0.3)
    if isinstance(raw, dict):
        raw = raw.get("content", "")

    parsed = _extract_json(raw)
    return ReplySummary(
        summary=parsed.get("summary", ""),
        action_items=parsed.get("action_items", []),
        priority=parsed.get("priority", "medium"),
        key_topics=parsed.get("key_topics", []),
    )


def _summarize_keywords(reply_text: str) -> ReplySummary:
    """Keyword-based fallback summarization."""
    sentences = [s.strip() for s in re.split(r"[.!?\n]", reply_text) if s.strip()]
    summary = sentences[0] if sentences else "No content."

    action_items = []
    lower = reply_text.lower()
    if any(kw in lower for kw in ["schedule", "meeting", "call", "zoom"]):
        action_items.append("Schedule meeting")
    if any(kw in lower for kw in ["deck", "presentation", "slides"]):
        action_items.append("Send pitch deck")
    if any(kw in lower for kw in ["documents", "data room", "financials"]):
        action_items.append("Share requested documents")
    if any(kw in lower for kw in ["question", "how", "what", "explain"]):
        action_items.append("Answer investor questions")

    priority = "medium"
    if any(kw in lower for kw in ["urgent", "asap", "today", "tomorrow"]):
        priority = "high"
    elif any(kw in lower for kw in ["whenever", "no rush", "sometime"]):
        priority = "low"

    return ReplySummary(
        summary=summary[:200],
        action_items=action_items or ["Review reply"],
        priority=priority,
        key_topics=[],
    )


def _extract_json(text: str) -> Dict[str, Any]:
    """Extract first JSON object from text."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    code_block = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if code_block:
        try:
            return json.loads(code_block.group(1).strip())
        except json.JSONDecodeError:
            pass
    brace_start = text.find("{")
    if brace_start != -1:
        depth = 0
        for i in range(brace_start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    return json.loads(text[brace_start : i + 1])
    raise ValueError("No valid JSON found.")
