# Web Scraping Skill

## Purpose

Scrape web page content using Firecrawl for markdown extraction and Tavily for search results.

## Inputs

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `url` | str | Yes | URL to scrape |
| `max_results` | int | No | Max search results (default: 4) |

## Outputs

```json
{
  "content": "markdown content...",
  "source": "firecrawl|tavily",
  "url": "string"
}
```

## Execution Steps

### Firecrawl Scrape

1. Initialize Firecrawl client
2. Call scrape endpoint with URL
3. Extract markdown content
4. Limit to 4000 characters
5. Return content

### Tavily Search

1. Initialize Tavily client
2. Build search query
3. Execute search
4. Parse results with url/content/score
5. Return list of results

## Validation Rules

- URL must be valid HTTP(S) URL
- Content must be non-empty
- Markdown conversion successful

## Failure Handling

| Error | Action |
|-------|--------|
| Invalid URL | Return error |
| Rate limited | Wait 60s, retry once |
| Scraping fails | Return empty content |
| Network error | Return error with fallback |

## Tools

### FirecrawlService

- Converts URLs to markdown
- Supports JavaScript rendering
- Career page inference (`/careers`)

### TavilyService

- Web search API
- Returns structured results
- Max 4 results per query

## Examples

```python
# Firecrawl scrape
firecrawl = FirecrawlService()
content = await firecrawl.scrape_url("https://acme.com/about")

# Tavily search
tavily = TavilyService()
results = await tavily.search("Acme Corp funding news", max_results=4)
```

## Integration

- **Services**: `FirecrawlService`, `TavilyService`
- **APIs**: Firecrawl API, Tavily Search API
- **Rate Limits**: Firecrawl (100 pages/month), Tavily (1000 queries/month)
- **Auth**: API keys required