"""
Email Tools for the Outreach Writer and Follow-up Agents.

Provides spam analysis, readability scoring, and email template generation
to help craft high-quality outreach emails.
"""

import json
import math
import re
import logging
from typing import Type
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

SPAM_TRIGGER_WORDS: list[str] = [
    "act now", "apply now", "buy now", "call now", "click here",
    "click below", "deal ending", "do it today", "don't delete",
    "don't hesitate", "double your", "earn extra", "exclusive deal",
    "expire", "extra income", "free", "free access", "free gift",
    "free trial", "great offer", "guarantee", "hurry", "immediately",
    "incredible deal", "limited time", "luxury", "make money",
    "million dollars", "miracle", "money back", "no catch",
    "no cost", "no obligation", "no risk", "offer expires",
    "once in a lifetime", "order now", "please read", "promise",
    "pure profit", "risk free", "satisfaction guaranteed",
    "special promotion", "this isn't spam", "urgent", "winner",
    "you have been selected", "you're a winner", "100% free",
    "100% satisfied", "cash bonus", "congratulations",
]


class SpamCheckInput(BaseModel):
    """Input schema for the Email Analysis Tool."""
    email_content: str = Field(
        ...,
        description="The full body text of the email to analyze.",
    )
    subject: str = Field(
        default="",
        description="The subject line of the email to analyze.",
    )


class EmailAnalysisTool:
    """
    Analyzes email content for spam triggers, readability score,
    and improvement suggestions to maximize deliverability.
    """

    def __init__(self):
        self.name = "Email Analysis Tool"
        self.description = (
            "Analyze email content for spam triggers, readability score, "
            "and improvement suggestions to maximize deliverability and engagement."
        )

    def run(self, email_content: str, subject: str = "") -> str:
        return self._run(email_content, subject)

    def _run(self, email_content: str, subject: str = "") -> str:
        """Analyze email content and return a comprehensive report."""
        full_text = f"{subject} {email_content}".lower()

        found_triggers: list[str] = []
        for trigger in SPAM_TRIGGER_WORDS:
            if trigger in full_text:
                found_triggers.append(trigger)

        spam_score = min(len(found_triggers) * 8, 100)

        readability = self._calculate_readability(email_content)

        word_count = len(email_content.split())
        sentence_count = max(len(re.split(r'[.!?]+', email_content)), 1)
        avg_sentence_length = word_count / sentence_count

        has_personalization = any(
            tok in email_content.lower()
            for tok in ["{name}", "{company}", "{{", "personali"]
        )
        has_cta = any(
            phrase in email_content.lower()
            for phrase in [
                "schedule a call", "book a meeting", "let me know",
                "would you be open", "reply", "interested in",
                "happy to chat", "quick call", "15 minutes",
            ]
        )
        has_unsubscribe = any(
            phrase in email_content.lower()
            for phrase in ["unsubscribe", "opt out", "opt-out", "stop receiving"]
        )

        link_count = len(re.findall(r'https?://', email_content))
        excessive_links = link_count > 3

        caps_words = len(re.findall(r'\b[A-Z]{2,}\b', email_content))
        excessive_caps = caps_words > 3

        suggestions: list[str] = []
        if spam_score > 20:
            suggestions.append(
                f"Remove or rephrase spam triggers: {', '.join(found_triggers[:5])}"
            )
        if word_count > 200:
            suggestions.append(
                f"Email is {word_count} words — aim for 50-150 words for cold outreach."
            )
        if word_count < 30:
            suggestions.append("Email may be too short to convey value. Aim for 50+ words.")
        if avg_sentence_length > 20:
            suggestions.append("Sentences are long. Break them up for better readability.")
        if not has_cta:
            suggestions.append("Add a clear, low-friction call to action.")
        if not has_personalization:
            suggestions.append("Add personalization tokens (lead name, company, etc.).")
        if excessive_links:
            suggestions.append("Too many links can trigger spam filters. Keep to 1-2 max.")
        if excessive_caps:
            suggestions.append("Reduce ALL-CAPS words — they trigger spam filters.")
        if not has_unsubscribe:
            suggestions.append(
                "Consider adding an unsubscribe/opt-out line for compliance."
            )

        deliverability_score = max(
            0,
            100
            - spam_score
            - (15 if excessive_links else 0)
            - (10 if excessive_caps else 0)
            - (10 if word_count > 250 else 0),
        )

        result = {
            "spam_analysis": {
                "score": spam_score,
                "triggers_found": found_triggers,
                "risk_level": (
                    "low" if spam_score < 15
                    else "medium" if spam_score < 40
                    else "high"
                ),
            },
            "readability": {
                "flesch_score": readability,
                "grade_level": self._flesch_to_grade(readability),
                "avg_sentence_length": round(avg_sentence_length, 1),
                "word_count": word_count,
            },
            "structure": {
                "has_personalization": has_personalization,
                "has_cta": has_cta,
                "has_unsubscribe": has_unsubscribe,
                "link_count": link_count,
            },
            "deliverability_score": deliverability_score,
            "suggestions": suggestions,
        }

        return json.dumps(result, indent=2)

    @staticmethod
    def _count_syllables(word: str) -> int:
        """Rough syllable count heuristic for English words."""
        word = word.lower().strip()
        if not word:
            return 0
        if len(word) <= 3:
            return 1
        vowels = "aeiouy"
        count = 0
        prev_vowel = False
        for char in word:
            is_vowel = char in vowels
            if is_vowel and not prev_vowel:
                count += 1
            prev_vowel = is_vowel
        if word.endswith("e") and count > 1:
            count -= 1
        return max(count, 1)

    def _calculate_readability(self, text: str) -> float:
        """Calculate Flesch Reading Ease score."""
        sentences = [s.strip() for s in re.split(r'[.!?]+', text) if s.strip()]
        words = text.split()
        if not words or not sentences:
            return 0.0

        total_syllables = sum(self._count_syllables(w) for w in words)
        word_count = len(words)
        sentence_count = len(sentences)

        score = (
            206.835
            - 1.015 * (word_count / sentence_count)
            - 84.6 * (total_syllables / word_count)
        )
        return round(max(0, min(score, 100)), 1)

    @staticmethod
    def _flesch_to_grade(score: float) -> str:
        """Convert Flesch score to a human-readable grade label."""
        if score >= 80:
            return "Easy (6th grade)"
        if score >= 60:
            return "Standard (8th-9th grade)"
        if score >= 40:
            return "Fairly Difficult (10th-12th grade)"
        if score >= 20:
            return "Difficult (College level)"
        return "Very Difficult (Graduate level)"


def email_template_tool(tone: str, context: str) -> str:
    """
    Generate an email template structure based on the specified tone and context.
    """
    tone = tone.lower().strip()

    templates = {
        "professional": {
            "greeting": "Dear {lead_name},",
            "opener_style": (
                "Reference a specific achievement or recent company news. "
                "Keep it formal but warm."
            ),
            "body_structure": [
                "Acknowledge their work or company milestone.",
                "Introduce your value proposition tied to their specific situation.",
                "Provide a brief, concrete proof point (case study or metric).",
            ],
            "cta_style": (
                "Would you be open to a brief 15-minute call next week "
                "to explore how we might help?"
            ),
            "closing": "Best regards,",
            "tone_guidelines": [
                "Use formal but approachable language.",
                "Avoid slang or overly casual expressions.",
                "Keep sentences concise and well-structured.",
                "Use data and specifics over vague claims.",
            ],
        },
        "casual": {
            "greeting": "Hey {lead_name},",
            "opener_style": (
                "Start with something relatable — a shared interest, "
                "mutual connection, or industry observation."
            ),
            "body_structure": [
                "Open with a human, conversational observation.",
                "Quickly explain why you're reaching out in 1-2 sentences.",
                "Drop a relevant result or insight without being salesy.",
            ],
            "cta_style": (
                "Curious if this resonates — happy to share more "
                "if you're up for a quick chat?"
            ),
            "closing": "Cheers,",
            "tone_guidelines": [
                "Write like you're emailing a colleague.",
                "Use contractions and natural language.",
                "Keep it short — under 100 words ideally.",
                "Avoid corporate jargon.",
            ],
        },
        "friendly": {
            "greeting": "Hi {lead_name}!",
            "opener_style": (
                "Lead with genuine enthusiasm about something they've done. "
                "Show you've done your homework."
            ),
            "body_structure": [
                "Compliment a specific accomplishment genuinely.",
                "Connect their work to what you offer naturally.",
                "Offer genuine help or a useful resource, no strings attached.",
            ],
            "cta_style": (
                "I'd love to hear your thoughts — no pressure at all, "
                "just thought this might be useful!"
            ),
            "closing": "Warm regards,",
            "tone_guidelines": [
                "Be genuinely warm and enthusiastic.",
                "Use exclamation points sparingly (1-2 max).",
                "Show authentic interest in their work.",
                "Offer value before asking for anything.",
            ],
        },
        "urgent": {
            "greeting": "Hi {lead_name},",
            "opener_style": (
                "Lead with a timely, relevant trigger — a deadline, "
                "market shift, or competitive development."
            ),
            "body_structure": [
                "Highlight a time-sensitive opportunity or risk.",
                "Explain the cost of inaction or delay briefly.",
                "Present your solution as the fastest path to resolution.",
            ],
            "cta_style": (
                "Can we connect this week? I have some insights "
                "that could help you get ahead of this."
            ),
            "closing": "Looking forward to connecting,",
            "tone_guidelines": [
                "Create urgency without being pushy or spammy.",
                "Use specific dates or timeframes when possible.",
                "Focus on their potential loss, not your product features.",
                "Avoid ALL CAPS and excessive exclamation marks.",
            ],
        },
    }

    template = templates.get(tone, templates["professional"])

    result = {
        "tone": tone if tone in templates else "professional",
        "context": context,
        "template": template,
        "usage_notes": (
            "Replace {lead_name} with the actual lead name. "
            "Customize the opener and body using the provided research data. "
            "Always run the final email through the Email Analysis Tool."
        ),
    }

    return json.dumps(result, indent=2)