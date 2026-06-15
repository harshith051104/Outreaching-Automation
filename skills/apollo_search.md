# Apollo Search Skill

## Purpose

Search for leads on Apollo.io using job titles, companies, locations, and industry filters.

## Inputs

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `job_titles` | list[str] | Yes | Job titles to search for |
| `locations` | list[str] | No | Geographic locations |
| `industry` | str | No | Industry vertical |
| `limit` | int | No | Maximum results (default: 10) |

## Outputs

```json
{
  "leads": [
    {
      "name": "string",
      "title": "string",
      "company": "string",
      "email": "string",
      "linkedin": "string",
      "website": "string"
    }
  ],
  "count": "number",
  "source": "apollo"
}
```

## Execution Steps

1. Initialize Apollo client with API key
2. Build search query from job titles
3. Execute search with filters
4. Parse and structure results
5. Return lead list

## Validation Rules

- `job_titles` must not be empty
- `limit` must be 1-100
- Each lead must have name or email

## Failure Handling

| Error | Action |
|-------|--------|
| Invalid API key | Return error, suggest checking key |
| Rate limited | Wait 60s, retry once |
| No results | Return empty array |
| Network error | Return error with fallback suggestion |

## Examples

### Search by Job Titles

```python
apollo_service = ApolloService()
leads = await apollo_service.search_leads(
    job_titles=["VP of Sales", "Director of Sales"],
    locations=["San Francisco"],
    industry="SaaS",
    limit=10
)
```

### Fallback Chain

```
Apollo → Tavily → Firecrawl → Empty Result
```

## Integration

- **Service**: `ApolloService`
- **API**: Apollo.io REST API
- **Rate Limits**: 100 requests/minute
- **Auth**: API key in header