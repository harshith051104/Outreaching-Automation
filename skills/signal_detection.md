# Signal Detection Skill

## Purpose

Detect and extract business signals (hiring, funding, tech changes, expansions) from web data for sales opportunities.

## Inputs

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `company_name` | str | Yes | Company to analyze |
| `raw_context` | list[str] | Yes | Scraped web content |
| `website_url` | str | No | Company website |

## Outputs

```json
{
  "signals": [
    {
      "signal": "Hiring SDRs",
      "category": "Sales Expansion",
      "score": 90,
      "hook": "Noticed you're expanding your sales team...",
      "description": "Scraped job post details",
      "source": "url"
    }
  ],
  "growth_indicators": ["string"],
  "personalization_angles": ["string"],
  "recommended_hooks": ["string"]
}
```

## Signal Categories

| Category | Description | Urgency |
|----------|-------------|---------|
| `Sales Expansion` | Hiring sales, SDRs, AEs | High |
| `Funding` | Raised rounds, investments | High |
| `Tech Stack Update` | New tools, infrastructure | Medium |
| `Product Launch` | New product, features | Medium |
| `Expansion` | New offices, markets | Medium |
| `Pricing Adjustment` | Changed pricing model | Low |

## Execution Steps

1. Compile raw context strings
2. Call LLM with signal extraction prompt
3. Parse JSON response
4. Sort signals by score descending
5. Generate hooks for each signal

## Scoring Rules

- Score 0-100 based on sales urgency
- Hiring SDRs: 80-95
- Recent funding: 70-90
- Tech changes: 50-70
- No signals: 0

## Validation Rules

- Signals must be non-empty array
- Score must be 0-100
- Category must be valid enum
- Hook must be non-empty string

## Failure Handling

| Error | Action |
|-------|--------|
| LLM parse fails | Return empty signals |
| No context | Return low confidence |
| Rate limited | Wait and retry once |

## Examples

```python
signal_service = SignalService()
signals = await signal_service.gather_and_store_signals(
    lead_id="lead_123",
    company_name="Acme Corp",
    website_url="https://acme.com"
)
```

## Integration

- **Service**: `SignalService`
- **LLM**: Groq via UnifiedLLMRouter
- **Storage**: MongoDB + Qdrant
- **Freshness Model**: `100 * exp(-0.02 * days_elapsed)`