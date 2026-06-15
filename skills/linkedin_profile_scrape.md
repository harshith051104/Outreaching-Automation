# LinkedIn Profile Scrape Skill

## Purpose

Scrape a LinkedIn profile page using Playwright to extract structured contact and professional data.

## Inputs

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `linkedin_url` | str | Yes | LinkedIn profile URL |
| `session_cookies` | dict | Yes | Encrypted session cookies |

## Outputs

```json
{
  "name": "string",
  "headline": "string",
  "about": "string",
  "location": "string",
  "experience": [{"title": "string", "company": "string", "duration": "string"}],
  "education": [{"school": "string", "degree": "string"}],
  "skills": ["string"],
  "connection_count": "string",
  "profile_url": "string"
}
```

## Execution Steps

- Validate session cookies are active
- Navigate to LinkedIn profile URL via Playwright
- Wait for profile content to load (3-5 second delay)
- Extract name from profile header
- Extract headline and location
- Extract about section
- Extract experience entries
- Extract education entries
- Extract top skills
- Return structured profile data

## Validation Rules

- Profile URL must be a valid LinkedIn URL
- Session must be authenticated
- At least name and headline must be extracted
- Random delay 2-5 seconds between page actions

## Failure Handling

| Error | Action |
|-------|--------|
| Session expired | Return error requesting re-authentication |
| Profile not found | Return empty profile with error flag |
| Page timeout | Retry once with longer timeout |
| Rate limited | Wait 60 seconds and retry |

## Integration

- **Service**: `linkedin_outreach_service.py`
- **Automation**: Playwright Chromium
- **Action**: `linkedin_profile_scrape`
