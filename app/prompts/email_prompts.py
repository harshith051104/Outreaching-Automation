"""Email writing prompts for agents."""

EMAIL_WRITING_PROMPT = """Write a cold outreach email for {lead_name} ({role} at {company}).

Personalization context:
{personalization_context}

Tone: {tone}
Word limit: 100-150 words

Requirements:
- Subject line: 4-8 words, lowercase, no spam words
- Opening: Reference something specific about the lead
- Body: Value-focused, scannable, single CTA
- No links in first email
- Both HTML and plain text versions
"""
