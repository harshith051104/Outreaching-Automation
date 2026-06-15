# Follow-up Generation Skill

## Purpose

Generate strategic follow-up emails that re-engage prospects with varied approaches based on sequence position and engagement signals.

## Inputs

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `original_email` | dict | Yes | Original email (subject, body_text) |
| `lead_data` | dict | Yes | Lead info (name, company, role) |
| `sequence_number` | int | Yes | Which follow-up (1, 2, 3, 4+) |
| `engagement_data` | dict | Yes | Engagement signals |

## Engagement Data Schema

```json
{
  "opened": true,
  "clicked": false,
  "open_count": 2,
  "replied": false,
  "reply_snippet": "string"
}
```

## Outputs

```json
{
  "subject": "follow-up subject line",
  "body_html": "<p>HTML version...</p>",
  "body_text": "Plain text version...",
  "recommended_delay_hours": 96,
  "approach_used": "value-add|social-proof|urgency|breakup",
  "new_value_added": "string",
  "is_reply_thread": true
}
```

## Execution Steps

1. Analyze engagement signals
2. Determine approach based on sequence number
3. Build prompt with context
4. Call LLM to generate follow-up
5. Return with recommended delay

## Approach by Sequence

| Sequence | Approach | Delay |
|----------|----------|-------|
| 1 | Value-add | 72-96 hours |
| 2 | Social proof | 120-168 hours |
| 3 | Urgency | 168-240 hours |
| 4+ | Breakup | 336+ hours |

## Engagement-Based Adjustments

| Signal | Adjustment |
|--------|------------|
| No opens | Use different subject |
| Opens, no reply | Change value prop |
| Multiple opens | Lower barrier CTA |
| Clicked, no reply | Be direct |

## Validation Rules

- Body: < 100 words
- Valid sequence number
- Subject different from original
- New value proposition clear

## Failure Handling

| Error | Action |
|-------|--------|
| LLM fails | Return template fallback |
| Invalid sequence | Use 4 (breakup) approach |
| Missing engagement | Use generic sequence |

## Examples

```python
followup = await generate_followup(
    original_email=orig,
    lead_data=lead_info,
    sequence_number=2,
    engagement_data=engagement
)
```

## Integration

- **Agent**: `followup_agent.py`
- **LLM**: Groq via get_groq_llm()
- **Prompts**: `followup_prompts.SEQUENCE_VARIATIONS`