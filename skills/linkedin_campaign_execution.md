# LinkedIn Campaign Execution Skill

## Purpose

Execute a single campaign step for one lead, orchestrating the appropriate workflow based on the action type.

## Inputs

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `campaign_id` | str | Yes | LinkedIn campaign ID |
| `lead_id` | str | Yes | Target lead ID |
| `action_type` | str | Yes | connection_request, message, followup |
| `user_id` | str | Yes | Current user ID |

## Outputs

```json
{
  "success": true,
  "action_id": "string",
  "action_type": "connection_request",
  "status": "pending_approval",
  "draft_message": "string"
}
```

## Execution Steps

- Load lead data from existing leads collection
- Check daily limits for the action type
- Based on action_type, invoke the appropriate workflow
- For connection_request: invoke linkedin_connection workflow
- For message: invoke linkedin_message workflow
- For followup: invoke linkedin_followup workflow
- Save action to linkedin_actions collection
- Return action draft for approval

## Validation Rules

- Lead must have a LinkedIn URL
- Daily limits must not be exceeded
- Campaign must be active
- Action type must be valid

## Failure Handling

| Error | Action |
|-------|--------|
| Lead has no LinkedIn URL | Skip with warning |
| Daily limit reached | Queue for next day |
| Workflow fails | Mark action as failed, continue campaign |

## Integration

- **Agent**: `linkedin_campaign_agent`
- **Workflows**: `linkedin_connection.yaml`, `linkedin_followup.yaml`
- **Action**: `linkedin_campaign_execution`
