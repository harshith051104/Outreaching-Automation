"""Follow-up generation prompts for CrewAI agents."""

FOLLOWUP_PROMPT = """Generate follow-up #{sequence_number} email for {lead_name}.

Original subject: {original_subject}
Engagement signals: {engagement_signals}

Strategy by sequence number:
1: Add value (share insight or resource)
2: Social proof (customer success story)
3: Create urgency (legitimate timing)
4+: Final/breakup email (easy to say no)

Requirements:
- Under 100 words
- Different subject approach (Re: or new angle)
- Add new value, never just "bumping this"
- Both HTML and plain text versions
"""

SEQUENCE_VARIATIONS = {
    1: "value-add — share a relevant insight",
    2: "social-proof — share a success story",
    3: "urgency — legitimate business reason to respond",
    4: "breakup — respectful final outreach",
}