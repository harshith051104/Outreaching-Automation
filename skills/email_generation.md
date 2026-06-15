# Email Generation Skill

## Purpose

Generate cold emails with subject lines, HTML body, plain-text body, and CTA, validated against spam triggers.

## Inputs

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `lead_data` | dict | Yes | Basic lead info |
| `personalization_data` | dict | Yes | Personalization elements |
| `tone` | str | No | professional/casual/friendly/urgent |
| `reference_data` | dict | No | Research and context |

## Outputs

```json
{
  "subject": "short personalized subject line",
  "body_html": "<p>HTML version...</p>",
  "body_text": "Plain text version...",
  "cta": "The specific call to action used",
  "word_count": 95,
  "spam_check_passed": true,
  "spam_score": 8,
  "tone_used": "professional"
}
```

## Execution Steps

1. Build email prompt with lead data and personalization
2. Call LLM to generate email content
3. Parse JSON response
4. Run spam analysis
5. If spam score > 15, revise and recheck
6. Return final email

## Spam Check Rules

| Trigger | Weight |
|---------|--------|
| Spam word found | +8 per word |
| Excessive links (> 3) | +15 |
| Excessive caps | +10 |
| Very long (> 250 words) | +10 |

## Spam Trigger Words

```python
SPAM_TRIGGERS = [
    "act now", "apply now", "buy now", "free", "guarantee",
    "urgent", "limited time", "winner", "congratulations"
]
```

## Deliverability Score

```
score = 100 - spam_score - excessive_links - excessive_caps - length_penalty
```

| Score | Risk Level |
|-------|------------|
| > 85 | Low |
| 60-85 | Medium |
| < 60 | High |

## Validation Rules

- Subject: 4-8 words
- Body: 50-150 words
- Spam score < 15
- Both HTML and text versions

## Failure Handling

| Error | Action |
|-------|--------|
| LLM fails | Return template fallback |
| Invalid JSON | Retry once |
| Spam score high | Auto-revise once |

## Examples

```python
email_content = await write_outreach_email(
    lead_data=lead_info,
    personalization_data=personalization,
    tone="professional"
)
```

## Integration

- **Agent**: `outreach_writer_agent.py`
- **LLM**: Groq via get_groq_llm()
- **Tool**: `EmailAnalysisTool`