# LinkedIn Send Connection Skill

## Purpose

Execute a LinkedIn connection request via Playwright browser automation after human approval.

## Inputs

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `linkedin_url` | str | Yes | Target profile URL |
| `connection_note` | str | Yes | Approved connection note |
| `session_cookies` | dict | Yes | Active session cookies |

## Outputs

```json
{
  "success": true,
  "action": "connection_sent",
  "linkedin_url": "string",
  "timestamp": "ISO datetime"
}
```

## Execution Steps

- Validate session is active
- Navigate to target LinkedIn profile
- Wait for page load (random 2-5s delay)
- Click Connect button
- Add personalized note
- Submit connection request
- Verify confirmation message appears
- Return success/failure status

## Validation Rules

- Session must be authenticated
- Daily connection limit not exceeded
- Connection note is ≤ 300 characters
- Action must be pre-approved by user

## Failure Handling

| Error | Action |
|-------|--------|
| Session expired | Return error, mark action as failed |
| Already connected | Skip, mark as already_connected |
| Connect button not found | Return error with screenshot context |
| Rate limited by LinkedIn | Wait and mark for retry |

## Integration

- **Service**: `linkedin_outreach_service.py`
- **Automation**: Playwright Chromium
- **Action**: `linkedin_send_connection`
