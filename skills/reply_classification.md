# Reply Classification Skill

## Purpose

Classify email reply intent and sentiment to determine lead priority and next actions.

## Inputs

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `reply_text` | str | Yes | The reply email text |
| `original_email` | str | Yes | Original outreach subject |
| `lead_context` | dict | Yes | Lead info (name, company, role, lead_score) |

## Outputs

```json
{
  "classification": "interested|meeting_requested|not_interested|follow_up_later|spam",
  "sentiment": "positive|neutral|negative",
  "confidence_score": 0.85,
  "lead_score_delta": 15,
  "reasoning": "string",
  "key_signals": ["string"],
  "recommended_action": "string",
  "urgency": "high|medium|low"
}
```

## Execution Steps

1. Build classification prompt with all context
2. Call LLM to analyze reply
3. Parse JSON classification
4. Calculate lead score delta
5. Determine urgency
6. Return classification result

## Classification Rules

| Category | Indicators | Lead Delta |
|----------|------------|------------|
| interested | Questions, wants info | +10 to +20 |
| meeting_requested | Explicit meeting ask | +25 to +40 |
| not_interested | Decline, remove | -30 to -50 |
| follow_up_later | Timing objection | -5 to +5 |
| spam | OOO, auto-reply | 0 |

## Sentiment Detection

| Tone | Indicators |
|------|------------|
| positive | Thank, appreciate, interested |
| negative | Not interested, stop |
| neutral | No clear sentiment |

## Urgency Mapping

| Classification | Urgency |
|----------------|---------|
| meeting_requested | high |
| interested | medium |
| follow_up_later | medium |
| not_interested | low |
| spam | low |

## Validation Rules

- Valid classification category
- Confidence 0.0-1.0
- Lead delta within range
- Reasoning > 20 chars

## Failure Handling

| Error | Action |
|-------|--------|
| Ambiguous reply | Default to follow_up_later |
| LLM fails | Return low confidence default |
| Auto-reply detected | Classify as spam |

## Examples

```python
classification = await classify_reply(
    reply_text="Thanks for reaching out! Could you send more info?",
    original_email="Quick question about your platform",
    lead_context={"name": "John", "company": "Acme", "lead_score": 50}
)
```

## Integration

- **Agent**: `reply_classification_agent.py`
- **LLM**: Groq via get_groq_llm()
- **Prompts**: `classification_prompts.REPLY_CLASSIFICATION_PROMPT`