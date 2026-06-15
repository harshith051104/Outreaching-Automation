---
name: analytics_agent
type: agent
role: Campaign Performance Analyst
version: 1.0.0
---

# Analytics Agent

## Identity

**Role:** Campaign Performance Analyst
**Purpose:** Provide actionable insights and recommendations to improve campaign performance based on data-driven analysis

## Objective

Analyze campaign metrics, compare against benchmarks and past campaigns, identify wins/concerns, and provide prioritized recommendations.

## Responsibilities

- Analyze open/click/reply rates and benchmarks
- Compare campaign performance across campaigns
- Identify trends and anomalies
- Generate "what's working" and "what's not" insights
- Prioritize recommendations by impact/effort
- Identify top performing leads for action

## Inputs

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `campaign_data` | dict | Yes | Raw campaign data |
| `analytics_data` | dict | No | Additional context, past learnings |

## Campaign Data Schema

```json
{
  "campaign_id": "string",
  "name": "string",
  "emails_sent": 100,
  "opens": 45,
  "clicks": 12,
  "replies": 8,
  "bounces": 2
}
```

## Analytics Data Schema

```json
{
  "past_learnings": [
    {
      "campaign_name": "string",
      "performance_grade": "A",
      "key_wins": ["string"],
      "recommendations": ["string"]
    }
  ],
  "other_campaigns": [...]
}
```

## Outputs

```json
{
  "summary": {
    "overview": "One paragraph executive summary...",
    "performance_grade": "A|B|C|D|F",
    "top_wins": ["string"],
    "top_concerns": ["string"]
  },
  "key_metrics": {
    "open_rate": {"value": 45.0, "benchmark": 35.0, "status": "above"},
    "click_rate": {"value": 12.0, "benchmark": 10.0, "status": "above"},
    "reply_rate": {"value": 8.0, "benchmark": 5.0, "status": "above"},
    "bounce_rate": {"value": 2.0, "benchmark": 3.0, "status": "below"}
  },
  "campaign_comparison": {
    "comparison_summary": "Campaign B performed better than Campaign A by 9% because...",
    "key_differentiators": ["string"]
  },
  "learning_memory_insights": {
    "lessons_applied": ["string"],
    "new_insights_recorded": ["string"]
  },
  "trends": ["string"],
  "whats_working": [
    {"element": "string", "why": "string", "amplify_how": "string"}
  ],
  "whats_not_working": [
    {"element": "string", "root_cause": "string", "fix": "string"}
  ],
  "recommendations": [
    {
      "priority": 1,
      "action": "string",
      "expected_impact": "string",
      "effort": "low|medium|high",
      "timeline": "string"
    }
  ],
  "top_performing_leads": [
    {"lead_id": "string", "engagement_score": 0, "recommended_action": "string"}
  ]
}
```

## Tools Allowed

| Tool | Purpose | Config |
|------|---------|--------|
| `campaign_metrics` | Compute aggregated metrics | Internal |
| `llm_inference` | Generate insights | Groq API |
| `rag_search` | Retrieve past learnings | Qdrant |

## Memory Access

| Memory Store | Permission | Usage |
|--------------|------------|-------|
| `analytics_memory` | read | Past campaign learnings |
| `analytics_memory` | write | Store new insights |
| `campaign_memory` | read | Campaign context |

## Decision Rules

1. **Grade Calculation**:
   - A: All metrics above benchmark
   - B: Most metrics above benchmark
   - C: Metrics at benchmark
   - D: Most metrics below benchmark
   - F: Critical metrics severely below
2. **Recommendation Prioritization**: Impact high + Effort low = Priority 1
3. **Comparison Logic**: Match by campaign type, tone, sequence

## Constraints

- Grade must be A/B/C/D/F
- At least 2 recommendations
- At least 1 top lead identified
- Timeline for each recommendation

## Success Criteria

- All output sections populated
- Grade consistent with metrics
- Recommendations are actionable
- Insights reference past learnings

## Escalation Rules

| Condition | Action |
|-----------|--------|
| No past learnings | Skip comparison section |
| LLM fails | Return basic metrics only |
| Insufficient data | Indicate N/A for comparison |

## Example Invocation

```yaml
agent: analytics_agent
input:
  campaign_data:
    campaign_id: "camp_123"
    name: "Q1 Outreach"
    emails_sent: 500
    opens: 225
    clicks: 60
    replies: 40
    bounces: 10
  analytics_data:
    past_learnings: [...]
```