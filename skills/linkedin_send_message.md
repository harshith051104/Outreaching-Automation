# LinkedIn Send Message Skill

## Purpose

Send a LinkedIn direct message via Playwright browser automation after human approval.

## Inputs

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `linkedin_url` | str | Yes | Target profile URL |
| `message_text` | str | Yes | Approved message text |
| `session_cookies` | dict | Yes | Active session cookies |

## Outputs

```json
{
  "success": true,
  "action": "message_sent",
  "linkedin_url": "string",
  "timestamp": "ISO datetime"
}
```

## Execution Steps

- Validate session is active
- Navigate to LinkedIn messaging
- Open conversation with target contact
- Wait for message input to load (random 2-5s delay)
- Type message text character by character (human-like)
- Send message
- Verify message appears in thread
- Return success/failure status

## Validation Rules

- Session must be authenticated
- Daily message limit not exceeded
- Must be connected to the target user
- Action must be pre-approved by user

## Failure Handling

| Error | Action |
|-------|--------|
| Session expired | Return error, mark action as failed |
| Not connected | Return error suggesting connection first |
| Message input not found | Retry once after page refresh |
| Rate limited | Wait and mark for retry |

## Integration

- **Service**: `linkedin_outreach_service.py`
- **Automation**: Playwright Chromium
- **Action**: `linkedin_send_message`
