# Opportunity Scoring Skill

## Purpose

Evaluate sales opportunities by analyzing signals and research to determine urgency, contact persona, and recommended offer.

## Inputs

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `company_name` | str | Yes | Company to evaluate |
| `research_context` | str | Yes | Company research data |
| `signals_context` | str | Yes | Extracted signals |
| `lead_id` | str | Yes | Associated lead ID |

## Outputs

```json
{
  "urgency": "High|Medium|Low",
  "best_contact": "CTO|VP of Sales|CEO|Other",
  "recommended_offer": "string",
  "confidence_score": 85,
  "reasoning": "string"
}
```

## Execution Steps

1. Fetch lead details from MongoDB
2. Retrieve signals for lead
3. Compile research and signal context
4. Call LLM with opportunity evaluation prompt
5. Parse and store result in opportunities collection

## Urgency Mapping

| Signal Type | Urgency |
|-------------|---------|
| Hiring SDRs/Sales | High |
| Recent funding (< 6 months) | High |
| Tech stack changes | Medium |
| Product launches | Medium |
| No recent signals | Low |

## Contact Persona Rules

| Signal Type | Best Contact |
|-------------|--------------|
| Sales hiring | VP of Sales |
| Tech changes | CTO |
| Funding | CEO |
| General | VP of Sales |

## Validation Rules

- Urgency must be High/Medium/Low
- Confidence must be 0-100
- Best contact must be valid persona
- Reasoning must be > 20 chars

## Failure Handling

| Error | Action |
|-------|--------|
| No signals | Default Medium urgency |
| LLM fails | Return default values |
| Lead not found | Return error |

## Examples

```python
signal_service = SignalService()
opportunity = await signal_service.evaluate_opportunity(lead_id="lead_123")
```

## Integration

- **Service**: `SignalService._run_opportunity_agent_llm()`
- **LLM**: Groq via UnifiedLLMRouter
- **Storage**: MongoDB `opportunities` collection