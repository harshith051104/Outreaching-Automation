"""
Intent analyzer — AI-powered reply intent classification.

Uses Groq LLM with extended investor taxonomy.
Falls back to keyword-based classification on LLM failure.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Optional

from reply.models import ReplyIntent, Sentiment, AnalysisResult, ReplySummary
from reply.config import reply_config
from reply.sentiment import analyze_sentiment_keywords, is_out_of_office, is_unsubscribe

logger = logging.getLogger(__name__)

# ── Investor-specific intent taxonomy ───────────────────────────────────
INTENT_TAXONOMY = {
    ReplyIntent.MEETING_REQUESTED: [
        "let's set up", "schedule a call", "free this week", "calendar",
        "meeting", "zoom", "call", "available tuesday", "available thursday",
    ],
    ReplyIntent.PITCH_DECK_REQUESTED: [
        "pitch deck", "deck", "presentation", "slides", "send deck",
        "share deck", "decks", "one pager", "one-pager",
    ],
    ReplyIntent.DATA_ROOM_REQUESTED: [
        "data room", "virtual data room", "documents", "financials",
        "share documents", "more details", "documentation",
    ],
    ReplyIntent.MORE_INFO_REQUESTED: [
        "tell me more", "more information", "learn more", "details",
        "could you share", "how does", "what does", "explain",
    ],
    ReplyIntent.TECHNICAL_QUESTIONS: [
        "how does it work", "architecture", "technical", "integration",
        "api", "scalability", "infrastructure", "technology stack",
    ],
    ReplyIntent.FINANCIAL_QUESTIONS: [
        "revenue", "margins", "unit economics", "ltv", "cac",
        "burn rate", "runway", "valuation", "financial",
    ],
    ReplyIntent.DUE_DILIGENCE_STARTED: [
        "due diligence", "dd", "deep dive", "evaluation", "assessing",
        "reviewing", "looking into", "analyzing",
    ],
    ReplyIntent.PARTNER_INTRO_REQUESTED: [
        "introduce to partner", "partner introduction", "connect with",
        "meet your team", "talk to someone",
    ],
    ReplyIntent.NOT_INTERESTED: [
        "not interested", "passing", "passed", "decline", "no thank",
        "not a fit", "not relevant", "don't contact", "remove",
    ],
    ReplyIntent.ALREADY_INVESTED: [
        "already invested", "already have", "existing portfolio",
        "competing", "similar", "conflict",
    ],
    ReplyIntent.PASSED_ON_OPPORTUNITY: [
        "passed on", "decided not to", "going in a different direction",
        "not proceeding", "won't be moving forward",
    ],
    ReplyIntent.WRONG_CONTACT: [
        "wrong person", "not the right", "you have the wrong",
        "i'm not", "contact the", "reach out to",
    ],
    ReplyIntent.FOLLOW_UP_LATER: [
        "not right now", "reach out next", "check back", "in a few months",
        "next quarter", "timing isn't", "timing isn't right",
        "budget freeze", "hiring freeze",
    ],
    ReplyIntent.REFERRAL: [
        "you should talk to", "i know someone", "let me connect you",
        "introduction", "referral",
    ],
    ReplyIntent.UNSUBSCRIBE: [
        "unsubscribe", "opt out", "remove me", "stop sending",
        "take me off",
    ],
}


def classify_intent_keywords(text: str) -> tuple[ReplyIntent, float]:
    """
    Fast keyword-based intent classification. No LLM calls.

    Returns (ReplyIntent, confidence).
    """
    if not text:
        return ReplyIntent.UNKNOWN, 0.3

    lower = text.lower()

    # Check OOO first
    if is_out_of_office(text):
        return ReplyIntent.OUT_OF_OFFICE, 0.85

    # Check unsubscribe
    if is_unsubscribe(text):
        return ReplyIntent.UNSUBSCRIBE, 0.9

    best_intent = ReplyIntent.UNKNOWN
    best_score = 0.0

    for intent, keywords in INTENT_TAXONOMY.items():
        score = sum(1 for kw in keywords if kw in lower)
        if score > best_score:
            best_score = score
            best_intent = intent

    if best_score == 0:
        return ReplyIntent.NEUTRAL_RESPONSE, 0.4

    confidence = min(0.5 + best_score * 0.12, 0.9)
    return best_intent, confidence


def classify_intent_llm(
    reply_text: str,
    original_email: str = "",
    lead_context: Optional[Dict[str, Any]] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    AI-powered intent classification using Groq LLM.

    Returns dict with intent, confidence, reasoning, key_signals.
    Falls back to keyword-based on LLM failure.
    """
    try:
        from app.services.llm_rate_gate import is_rate_limited
        if is_rate_limited():
            logger.info("Intent classification skipped — rate-limit gate active.")
            intent, conf = classify_intent_keywords(reply_text)
            return {
                "intent": intent.value,
                "confidence": conf,
                "reasoning": "LLM rate-limited; keyword fallback used.",
                "key_signals": [],
            }
    except ImportError:
        pass

    ctx = lead_context or {}
    lead_name = ctx.get("name", "Unknown")
    company = ctx.get("company", "Unknown")
    role = ctx.get("role", "Unknown")

    system_prompt = (
        "You are a Reply Intent Classifier for investor outreach. "
        "Classify the reply into exactly one intent category. "
        "Return JSON with: intent, confidence (0-1), reasoning (2-3 sentences), "
        "key_signals (list of strings)."
    )

    intent_list = "\n".join(f"- {i.value}" for i in ReplyIntent)

    user_prompt = f"""Classify this investor reply:

Lead: {lead_name} ({role}, {company})
Original email: {original_email[:500] if original_email else 'N/A'}

Reply:
---
{reply_text[:2000]}
---

Intent categories:
{intent_list}

Return JSON: {{"intent": "...", "confidence": 0.85, "reasoning": "...", "key_signals": [...]}}"""

    try:
        from app.services.llm_manager import LLMManager
        llm = LLMManager()
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        raw = llm.generate_completion(messages=messages, temperature=reply_config.llm_temperature)
        if isinstance(raw, dict):
            raw = raw.get("content", "")
        parsed = _extract_json(raw)
        # Validate intent value
        try:
            intent_val = ReplyIntent(parsed.get("intent", "unknown"))
        except ValueError:
            intent_val = ReplyIntent.UNKNOWN
        return {
            "intent": intent_val.value,
            "confidence": float(parsed.get("confidence", 0.5)),
            "reasoning": parsed.get("reasoning", ""),
            "key_signals": parsed.get("key_signals", []),
        }
    except Exception as exc:
        logger.warning("LLM intent classification failed: %s", exc)
        intent, conf = classify_intent_keywords(reply_text)
        return {
            "intent": intent.value,
            "confidence": conf,
            "reasoning": f"LLM failed ({exc}); keyword fallback used.",
            "key_signals": [],
        }


def analyze_reply(
    reply_text: str,
    original_email: str = "",
    lead_context: Optional[Dict[str, Any]] = None,
    user_id: Optional[str] = None,
    use_llm: bool = True,
) -> AnalysisResult:
    """
    Full intent + sentiment analysis. Main entry point.

    Args:
        reply_text: The clean reply text.
        original_email: The original outreach email.
        lead_context: Dict with name, company, role, lead_score.
        user_id: User ID for LLM rate limiting.
        use_llm: Whether to use LLM (False = keyword only).

    Returns:
        AnalysisResult with intent, sentiment, confidence, reasoning.
    """
    # 1. Sentiment (always keyword-based first)
    sentiment, sent_conf = analyze_sentiment_keywords(reply_text)

    # 2. Intent
    if use_llm:
        intent_result = classify_intent_llm(reply_text, original_email, lead_context, user_id)
    else:
        intent, conf = classify_intent_keywords(reply_text)
        intent_result = {
            "intent": intent.value,
            "confidence": conf,
            "reasoning": "Keyword-based classification.",
            "key_signals": [],
        }

    try:
        intent = ReplyIntent(intent_result["intent"])
    except ValueError:
        intent = ReplyIntent.UNKNOWN

    # 3. Lead score delta
    from reply.models import INTENT_LEAD_STATUS_MAP
    delta = _compute_score_delta(intent)

    return AnalysisResult(
        intent=intent,
        intent_confidence=intent_result["confidence"],
        intent_reasoning=intent_result.get("reasoning", ""),
        sentiment=sentiment,
        sentiment_confidence=sent_conf,
        lead_score_delta=delta,
        key_signals=intent_result.get("key_signals", []),
        recommended_action=_get_recommended_action(intent),
        urgency=_get_urgency(intent),
    )


def _compute_score_delta(intent: ReplyIntent) -> float:
    """Compute lead score delta based on intent."""
    scoring = {
        ReplyIntent.MEETING_REQUESTED: 30.0,
        ReplyIntent.PITCH_DECK_REQUESTED: 20.0,
        ReplyIntent.DATA_ROOM_REQUESTED: 25.0,
        ReplyIntent.DUE_DILIGENCE_STARTED: 25.0,
        ReplyIntent.INTERESTED: 15.0,
        ReplyIntent.MORE_INFO_REQUESTED: 15.0,
        ReplyIntent.TECHNICAL_QUESTIONS: 10.0,
        ReplyIntent.FINANCIAL_QUESTIONS: 15.0,
        ReplyIntent.PARTNER_INTRO_REQUESTED: 15.0,
        ReplyIntent.POSITIVE_RESPONSE: 10.0,
        ReplyIntent.REFERRAL: 15.0,
        ReplyIntent.NEUTRAL_RESPONSE: 5.0,
        ReplyIntent.TIMING_NOT_RIGHT: 0.0,
        ReplyIntent.FOLLOW_UP_LATER: 0.0,
        ReplyIntent.NOT_INTERESTED: -40.0,
        ReplyIntent.ALREADY_INVESTED: -30.0,
        ReplyIntent.PASSED_ON_OPPORTUNITY: -35.0,
        ReplyIntent.WRONG_CONTACT: -20.0,
        ReplyIntent.OUT_OF_OFFICE: 0.0,
        ReplyIntent.UNSUBSCRIBE: -50.0,
        ReplyIntent.SPAM: -10.0,
        ReplyIntent.UNKNOWN: 0.0,
    }
    return scoring.get(intent, 0.0)


def _get_recommended_action(intent: ReplyIntent) -> str:
    """Human-readable recommended action."""
    actions = {
        ReplyIntent.MEETING_REQUESTED: "Schedule a meeting within 24 hours.",
        ReplyIntent.PITCH_DECK_REQUESTED: "Send pitch deck promptly.",
        ReplyIntent.DATA_ROOM_REQUESTED: "Grant data room access.",
        ReplyIntent.DUE_DILIGENCE_STARTED: "Prepare due diligence materials.",
        ReplyIntent.INTERESTED: "Send follow-up with more details.",
        ReplyIntent.MORE_INFO_REQUESTED: "Provide requested information.",
        ReplyIntent.TECHNICAL_QUESTIONS: "Prepare technical deep-dive.",
        ReplyIntent.FINANCIAL_QUESTIONS: "Share financial overview.",
        ReplyIntent.PARTNER_INTRO_REQUESTED: "Facilitate partner introduction.",
        ReplyIntent.POSITIVE_RESPONSE: "Continue engagement.",
        ReplyIntent.NEUTRAL_RESPONSE: "Send follow-up in 3-5 days.",
        ReplyIntent.TIMING_NOT_RIGHT: "Schedule follow-up in 30 days.",
        ReplyIntent.FOLLOW_UP_LATER: "Schedule follow-up in 14 days.",
        ReplyIntent.NOT_INTERESTED: "Close lead. No further contact.",
        ReplyIntent.ALREADY_INVESTED: "Close lead. No further contact.",
        ReplyIntent.PASSED_ON_OPPORTUNITY: "Close lead. No further contact.",
        ReplyIntent.WRONG_CONTACT: "Update contact info or close lead.",
        ReplyIntent.OUT_OF_OFFICE: "Delay follow-up until OOO ends.",
        ReplyIntent.UNSUBSCRIBE: "Immediately stop all outreach.",
        ReplyIntent.REFERRAL: "Process referral and create task.",
        ReplyIntent.SPAM: "Close lead. No further contact.",
        ReplyIntent.UNKNOWN: "Review manually.",
    }
    return actions.get(intent, "Review manually.")


def _get_urgency(intent: ReplyIntent) -> str:
    """Urgency level for the reply."""
    high = {
        ReplyIntent.MEETING_REQUESTED, ReplyIntent.PITCH_DECK_REQUESTED,
        ReplyIntent.DATA_ROOM_REQUESTED, ReplyIntent.DUE_DILIGENCE_STARTED,
        ReplyIntent.PARTNER_INTRO_REQUESTED,
    }
    medium = {
        ReplyIntent.INTERESTED, ReplyIntent.MORE_INFO_REQUESTED,
        ReplyIntent.TECHNICAL_QUESTIONS, ReplyIntent.FINANCIAL_QUESTIONS,
        ReplyIntent.POSITIVE_RESPONSE, ReplyIntent.REFERRAL,
    }
    if intent in high:
        return "high"
    if intent in medium:
        return "medium"
    return "low"


def _extract_json(text: str) -> Dict[str, Any]:
    """Extract and parse the first JSON object from text."""
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
