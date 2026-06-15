"""Reply classification prompts for CrewAI agents."""

REPLY_CLASSIFICATION_PROMPT = """Classify this email reply:

From: {from_email}
Reply text: {reply_text}
Original email subject: {original_subject}

Classify into ONE of these categories:
- interested: Shows interest or asks questions
- meeting_requested: Explicitly requests a call/meeting
- not_interested: Clearly declines
- follow_up_later: Timing issue, not a rejection
- spam: Auto-reply, out-of-office, irrelevant

Return JSON with:
- classification: the category
- sentiment: positive/neutral/negative
- confidence_score: 0.0 to 1.0
- reasoning: brief explanation
- recommended_action: what to do next
"""