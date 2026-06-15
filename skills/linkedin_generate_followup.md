# LinkedIn Generate Follow-up Skill

## Purpose

Generate strategic LinkedIn follow-up messages that add new value based on relationship stage and conversation history.

## Inputs

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `lead_data` | dict | Yes | Lead profile info |
| `conversation_history` | array | Yes | Previous messages |
| `relationship_stage` | str | Yes | Current stage |
| `sequence_number` | int | Yes | Which follow-up (1-4+) |

## Outputs

```json
{
  "followup_message": "string (≤500 chars)",
  "recommended_delay_hours": 72,
  "approach_used": "value-add",
  "new_value_added": "Shared relevant industry insight"
}
```

## Execution Steps

- Analyze conversation history for context
- Determine approach based on sequence number
- Build prompt with relationship context
- Call LLM to generate follow-up
- Validate character limits
- Return with recommended timing

## Validation Rules

- Message must be ≤ 500 characters
- Must add new value (not just "bumping")
- Approach must match sequence position
- Clear CTA present

## Failure Handling

| Error | Action |
|-------|--------|
| LLM fails | Return template follow-up |
| No conversation history | Use generic value-add approach |

## Integration

- **Agent**: `linkedin_followup_agent`
- **LLM**: Groq via llm_inference
- **Action**: `linkedin_generate_followup`
