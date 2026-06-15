# LinkedIn Generate Message Skill

## Purpose

Generate a personalized LinkedIn direct message optimized for the platform's conversational format.

## Inputs

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `lead_data` | dict | Yes | Lead profile info |
| `personalization_data` | dict | Yes | Personalization elements |
| `message_type` | str | Yes | first_message, reply |
| `conversation_history` | array | No | Previous messages |

## Outputs

```json
{
  "message_text": "string (≤500 chars)",
  "character_count": 420,
  "word_count": 65,
  "tone_used": "professional",
  "cta": "string"
}
```

## Execution Steps

- Build context from lead data and conversation history
- Call LLM to generate message
- Validate character count (≤500)
- Verify no links in first message
- Check for spam triggers
- Return final message with metadata

## Validation Rules

- Message must be ≤ 500 characters
- No links in first message
- Single clear CTA
- No spam trigger words
- Both first_message and reply types supported

## Failure Handling

| Error | Action |
|-------|--------|
| LLM fails | Return template fallback |
| Over character limit | Regenerate with stricter constraint |

## Integration

- **Agent**: `linkedin_message_agent`
- **LLM**: Groq via llm_inference
- **Action**: `linkedin_generate_message`
