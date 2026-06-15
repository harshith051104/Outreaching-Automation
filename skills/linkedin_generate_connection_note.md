# LinkedIn Generate Connection Note Skill

## Purpose

Generate a personalized LinkedIn connection request note (≤300 characters) using AI based on profile and research data.

## Inputs

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `lead_data` | dict | Yes | Lead profile info |
| `personalization_data` | dict | Yes | Personalization elements |
| `research_data` | dict | No | Company research |

## Outputs

```json
{
  "connection_note": "string (≤300 chars)",
  "character_count": 280,
  "tone_used": "professional",
  "personalization_hook": "string"
}
```

## Execution Steps

- Build prompt with lead profile and personalization data
- Call LLM to generate connection note
- Validate character count (≤300)
- If over limit, regenerate with stricter constraint
- Return final note with metadata

## Validation Rules

- Note must be ≤ 300 characters
- Must reference something specific about the prospect
- No links or URLs
- No spam trigger words
- Must feel human-written

## Failure Handling

| Error | Action |
|-------|--------|
| LLM fails | Return template: "Hi {name}, noticed your work at {company}. Would love to connect!" |
| Over character limit | Truncate intelligently at sentence boundary |

## Integration

- **Agent**: `linkedin_message_agent`
- **LLM**: Groq via llm_inference
- **Action**: `linkedin_generate_connection_note`
