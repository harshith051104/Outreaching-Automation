# LinkedIn Monitor Connections Skill

## Purpose

Check LinkedIn for newly accepted connections, pending invitations, and new messages.

## Inputs

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `session_cookies` | dict | Yes | Active session cookies |
| `user_id` | str | Yes | Current user ID |

## Outputs

```json
{
  "accepted_connections": [
    {"name": "string", "linkedin_url": "string", "accepted_at": "string"}
  ],
  "pending_invitations": [
    {"name": "string", "linkedin_url": "string", "sent_at": "string"}
  ],
  "new_messages": [
    {"from_name": "string", "linkedin_url": "string", "preview": "string"}
  ]
}
```

## Execution Steps

- Validate session is active
- Navigate to My Network > Invitations page
- Scrape accepted connection notifications
- Scrape pending sent invitations
- Navigate to Messaging inbox
- Scrape unread message previews
- Return structured update data

## Validation Rules

- Session must be authenticated
- Random delays between page navigations
- Only check once per monitoring cycle

## Failure Handling

| Error | Action |
|-------|--------|
| Session expired | Return empty results, flag session as expired |
| Page not loading | Retry once with longer timeout |
| Scraping fails | Return partial results |

## Integration

- **Service**: `linkedin_outreach_service.py`
- **Monitor**: `linkedin_connection_monitor.py`
- **Action**: `linkedin_monitor_connections`
