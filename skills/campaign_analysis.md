# Campaign Analysis Skill

## Purpose

Compute campaign metrics (open rate, click rate, reply rate) and provide benchmark comparisons.

## Inputs

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `campaign_id` | str | Yes | Campaign to analyze |
| `emails_sent` | int | Yes | Total emails sent |
| `tracking_events` | list[dict] | Yes | Open/click/reply events |

## Outputs

```json
{
  "emails_sent": 100,
  "emails_failed": 2,
  "unique_opens": 45,
  "unique_clicks": 12,
  "total_replies": 8,
  "open_rate": 45.0,
  "click_rate": 12.0,
  "reply_rate": 8.0,
  "bounce_rate": 2.0,
  "benchmarks": {
    "open_rate": {"typical": 35, "your_rate": 45, "status": "above"},
    "click_rate": {"typical": 10, "your_rate": 12, "status": "above"},
    "reply_rate": {"typical": 5, "your_rate": 8, "status": "above"}
  }
}
```

## Execution Steps

1. Count total emails sent/failed
2. Aggregate tracking events by type
3. Calculate unique opens/clicks
4. Compute rates as percentages
5. Compare to benchmarks
6. Return structured metrics

## Benchmark Values

| Metric | Benchmark |
|--------|-----------|
| Open Rate | 35% |
| Click Rate | 10% |
| Reply Rate | 5% |
| Bounce Rate | 3% |

## Rate Calculations

```
open_rate = (unique_opens / emails_sent) * 100
click_rate = (unique_clicks / emails_sent) * 100
reply_rate = (replies / emails_sent) * 100
bounce_rate = (bounces / emails_sent) * 100
```

## Status Mapping

| Condition | Status |
|-----------|--------|
| > benchmark + 5% | above |
| Within ±5% | at |
| < benchmark - 5% | below |

## Validation Rules

- Emails sent > 0
- Rates within 0-100 range
- Unique counts <= total events

## Failure Handling

| Error | Action |
|-------|--------|
| No events | Return zeros |
| Division by zero | Return 0 |
| Invalid campaign | Return error |

## Examples

```python
metrics = compute_campaign_metrics(
    campaign_id="camp_123",
    emails_sent=500,
    tracking_events=events
)
```

## Integration

- **Service**: `analytics_service.py`
- **Tools**: `CampaignMetricsTool`
- **Storage**: MongoDB `analytics` collection