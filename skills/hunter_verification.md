# Hunter Email Verification Skill

## Purpose

Verify email deliverability and validity using Hunter.io API. Discard undeliverable emails before outreach.

## Inputs

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `email` | str | Yes | Email address to verify |

## Outputs

```json
{
  "email": "string",
  "status": "verified|deliverable|undeliverable|unknown",
  "score": 85,
  "deliverable": true,
  "reason": "string"
}
```

## Execution Steps

1. Initialize Hunter client with API key
2. Call email verification endpoint
3. Parse response for status and score
4. Map to standard status values
5. Return verification result

## Validation Rules

- Email must match regex pattern
- Score must be 0-100
- Status must be valid enum value

## Failure Handling

| Error | Action |
|-------|--------|
| Invalid API key | Return error |
| Rate limited | Wait 60s, retry once |
| Invalid email format | Return "undeliverable" |
| Network error | Return "unknown" status |

## Status Mapping

| Hunter Status | Our Status |
|---------------|------------|
| valid | verified |
| deliverable | deliverable |
| undeliverable | undeliverable |
| accept_all | unknown |
| unknown | unknown |

## Examples

```python
hunter = HunterEnrichmentService()
result = await hunter.verify_email("john@acme.com")
if result.get("deliverable"):
    # Add to outreach list
```

## Integration

- **Service**: `HunterEnrichmentService`
- **API**: Hunter.io REST API
- **Rate Limits**: 50 requests/month (free tier)
- **Auth**: API key in query param