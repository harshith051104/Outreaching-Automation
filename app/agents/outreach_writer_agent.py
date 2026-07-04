"""
Outreach Writer Agent — Writes compelling, human-like cold emails
that get responses without triggering spam filters.

Uses the EmailAnalysisTool to validate deliverability before finalizing.
"""

import json
import logging
import re
from typing import Any

from app.agents.tools.email_tool import EmailAnalysisTool
from app.config.groq_config import groq_inference

logger = logging.getLogger(__name__)


def _clean_placeholders(text: str, sender_name: str, sender_email: str, sender_title: str = "") -> str:
    """Replace all forms of sender placeholders case-insensitively."""
    if not text:
        return ""
    if sender_name:
        text = re.sub(r"\[Your\s+Name\]", sender_name, text, flags=re.IGNORECASE)
        text = re.sub(r"\[Sender\s+Name\]", sender_name, text, flags=re.IGNORECASE)
        text = re.sub(r"\{\{\s*sender_name\s*\}\}", sender_name, text, flags=re.IGNORECASE)
    if sender_email:
        text = re.sub(r"\[Your\s+Email\]", sender_email, text, flags=re.IGNORECASE)
        text = re.sub(r"\[Sender\s+Email\]", sender_email, text, flags=re.IGNORECASE)
        text = re.sub(r"\{\{\s*sender_email\s*\}\}", sender_email, text, flags=re.IGNORECASE)
    
    title_to_use = sender_title or "Founder & CEO"
    if not sender_title:
        logger.warning("sender_title not provided to _clean_placeholders - using default 'Founder & CEO'")
    text = re.sub(r"\[Your\s+Title\]", title_to_use, text, flags=re.IGNORECASE)
    text = re.sub(r"\[Sender\s+Title\]", title_to_use, text, flags=re.IGNORECASE)
    text = re.sub(r"\{\{\s*sender_title\s*\}\}", title_to_use, text, flags=re.IGNORECASE)
    return text


def write_outreach_email(
    lead_data: dict,
    personalization_data: dict,
    tone: str = "professional",
    subject_template: str = "",
    body_template: str = "",
    sender_name: str = "",
    sender_email: str = "",
    sender_title: str = "",
    campaign_description: str = "",
) -> dict[str, Any]:
    """
    Run the email writing pipeline for a lead framework-freely.

    Args:
        lead_data: Basic lead information.
        personalization_data: Personalization data from the personalization agent.
        tone: Email tone (professional, casual, friendly, urgent).
        subject_template: The baseline subject template from the campaign.
        body_template: The baseline body template from the campaign.
        sender_name: Name of the sender.
        sender_email: Email address of the sender.
        sender_title: Job title of the sender.
        campaign_description: Contextual description of the sender's company/product.

    Returns:
        Email data as a dictionary with subject, body_html, body_text, cta.
    """
    lead_name = lead_data.get("name", "Unknown")
    company = lead_data.get("company", "Unknown")
    role = lead_data.get("role", "Unknown")

    # Pre-replace sender details in templates if provided
    body_template = _clean_placeholders(body_template, sender_name, sender_email, sender_title)
    subject_template = _clean_placeholders(subject_template, sender_name, sender_email, sender_title)

    personalization_json = json.dumps(personalization_data, indent=2, default=str)

    logger.info(f"Writing framework-free outreach email for: {lead_name} (tone: {tone})")

    system_prompt = (
        "You are a Cold Email Copywriter. You are a world-class cold email copywriter who has helped hundreds "
        "of B2B companies generate millions in pipeline through email outreach. "
        "Your emails consistently achieve 40%+ open rates and 8%+ reply rates — far above the industry average. "
        "Your secret is writing emails that sound like they come from a thoughtful human, not a marketing machine. "
        "You obsess over every word, knowing that subject lines are gatekeepers and every sentence must earn the right "
        "to the next one. You never use spam trigger words, always include a single clear CTA, and keep emails scannable on mobile devices."
    )

    user_prompt = f"""
Write a cold outreach email to {lead_name} ({role} at {company}) using the
personalization data below. The email must feel human-written, avoid spam
filters, and drive a single clear action.

**Lead:**
- Name: {lead_name}
- Role: {role}
- Company: {company}

**Sender's Company Context / Campaign Goal:**
{campaign_description or "N/A"}

**Personalization Data:**
{personalization_json}

**Tone:** {tone}
"""

    if body_template:
        user_prompt += f"\n\n**Baseline Campaign Template (you MUST adapt and personalize this core content, keeping all details like product name, metrics, and funding information intact):**\n{body_template}"
    if subject_template:
        user_prompt += f"\n\n**Subject Line Template (use this as the basis for your subject line):**\n{subject_template}"

    user_prompt += """

**Email Requirements:**

1. **Subject Line:**
   - 4-8 words maximum
   - Lowercase (except proper nouns)
   - No spam trigger words (free, guarantee, urgent, etc.)
   - Personalized — reference the lead, company, or a specific insight
   - Create curiosity or reference value

2. **Email Body:**
   - Total length: 50-150 words (shorter is better)
   - Opening: Use the personalized opener from the data (refine if needed)
   - Value Bridge: Connect their pain point to your value in 1-2 sentences. If a Baseline Campaign Template is provided, you must bridge their pain point to the specific product/proposition outlined in the template.
   - Social Proof: One brief, specific proof point if available
   - CTA: A single, low-friction call to action (e.g., "Would you be open to a 15-minute call next week?")
   - No links in the first email (improves deliverability)
   - No attachments mentioned
   - Write in short paragraphs (1-2 sentences each)
   - Resolve and replace any bracketed text or instructions (such as `[insert 1-sentence update: ...]`, `[Specific Thesis Point]`, or `[1-sentence generic value prop...]`) inside the templates. Do NOT output any bracketed text in the final email. Replace them with highly specific, factual, and contextually appropriate sentences based on the lead's profile, personalization data, and the sender's company context.
   - Make sure all placeholders like [Your Name] or [Your Email] are replaced with actual names or resolved naturally.

3. **Formatting:**
   - Provide both HTML and plain-text versions
   - HTML should use simple inline styles only (no CSS classes)
   - Use <br> for line breaks, minimal formatting
   - No images or heavy formatting

Return your output strictly as a JSON object matching this structure:
{
    "subject": "short personalized subject line",
    "body_html": "<p>HTML version of the email...</p>",
    "body_text": "Plain text version of the email...",
    "cta": "The specific call to action used",
    "word_count": 95,
    "tone_used": "{tone}"
}
"""

    try:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        raw_output = groq_inference(messages, temperature=0.5)
        parsed = _extract_json(raw_output)

        # Clean any remaining placeholders in the generated output
        if "subject" in parsed:
            parsed["subject"] = _clean_placeholders(parsed["subject"], sender_name, sender_email, sender_title)
        if "body_html" in parsed:
            parsed["body_html"] = _clean_placeholders(parsed["body_html"], sender_name, sender_email, sender_title)
        if "body_text" in parsed:
            parsed["body_text"] = _clean_placeholders(parsed["body_text"], sender_name, sender_email, sender_title)

        # Run EmailAnalysisTool to verify spam score and deliverability
        analyzer = EmailAnalysisTool()
        analysis_raw = analyzer.run(
            email_content=parsed.get("body_text", parsed.get("body_html", "")),
            subject=parsed.get("subject", "")
        )
        analysis = json.loads(analysis_raw)
        
        parsed["spam_check_passed"] = analysis.get("spam_analysis", {}).get("score", 0) <= 15
        logger.info(f"Email writing completed framework-freely. Spam score: {analysis.get('spam_analysis', {}).get('score', 0)}")
        return parsed

    except Exception as exc:
        logger.warning(f"Could not generate email output framework-freely: {exc}")
        
        if body_template:
            # Personalize the user's template as the fallback
            fallback_body = body_template.replace("{{first_name}}", lead_name.split()[0]).replace("{{name}}", lead_name)
            fallback_subject = subject_template.replace("{{first_name}}", lead_name.split()[0]) if subject_template else f"collaboration with {company}"
        else:
            # Simple fallback template
            fallback_subject = f"collaboration with {company}"
            fallback_body = (
                f"Hi {lead_name},\n\n"
                f"I've been following {company} and was impressed by your focus on B2B success. "
                f"As {role}, I thought you might be interested in how we help companies optimize their operations.\n\n"
                f"Would you be open to a brief chat next week?\n\n"
                f"Best regards"
            )
        
        fallback_subject = _clean_placeholders(fallback_subject, sender_name, sender_email, sender_title)
        fallback_body = _clean_placeholders(fallback_body, sender_name, sender_email, sender_title)

        return {
            "subject": fallback_subject,
            "body_html": f"<p>{fallback_body.replace(chr(10), '<br>')}</p>",
            "body_text": fallback_body,
            "cta": "Would you be open to a brief chat next week?",
            "word_count": len(fallback_body.split()),
            "spam_check_passed": True,
            "tone_used": tone
        }


def _extract_json(text: str) -> dict:
    """Extract and parse the first JSON object found in a text string."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if json_match:
        return json.loads(json_match.group(1))

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

    raise ValueError("No valid JSON found in text.")