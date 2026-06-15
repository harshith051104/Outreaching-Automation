# Lead Quality Scoring Skill

## Purpose

Calculate a quality score (0 to 100) for a lead profile based on completeness, job title fit, and email deliverability.

## Inputs

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `leads` | list | Yes | List of lead dictionaries |
| `job_titles` | list | Yes | Job titles to filter and score fit |

## Outputs

```json
{
  "scored_leads": [
    {
      "name": "string",
      "email": "string",
      "company": "string",
      "role": "string",
      "lead_quality_score": 85.0
    }
  ]
}
```

## Execution Steps

1. Parse input lead details (email, linkedin, company, role, website)
2. Score completeness (up to 40 points)
3. Score email deliverability using verification results (up to 40 points)
4. Score role and job titles alignment fit (up to 20 points)
5. Return scored leads dictionary

## Validation Rules

- Lead quality score must be between 0.0 and 100.0
- Inputs must contain list of leads

## Failure Handling

| Error | Action |
|-------|--------|
| Missing inputs | Return empty list of scored leads |
| Scoring exception | Assign default score of 10.0 |

## Examples

```python
scored = await calculate_quality_score(
    leads=[{"name": "Jane", "email": "jane@client.com"}],
    job_titles=["CEO", "Founder"]
)
```

## Integration

- **Service**: `LeadDiscoveryService._verify_and_store_leads()`
- **Implementation**: `engine.py` / `_calculate_quality_score`
