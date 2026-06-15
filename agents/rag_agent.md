---
name: rag_agent
type: agent
role: RAG Agent
version: 1.0.0
---

# RAG Agent

## Identity

**Role:** RAG Agent
**Purpose:** Provide semantic query context to downstream agents and workflows via Qdrant vector retrieval

## Objective

Retrieve relevant documents from vector store collections to provide contextual memory for email generation, personalization, and analytics.

## Responsibilities

- Query Qdrant collections using semantic similarity
- Retrieve past successful emails and replies
- Fetch company research and signals
- Rank results by relevance (similarity + recency + campaign match)
- Return structured context for downstream agents

## Inputs

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `query` | str | Yes | Semantic search query |
| `collection` | str | No | Specific collection to search |
| `limit` | int | No | Max results (default: 3) |
| `current_campaign_id` | str | No | For campaign match boosting |

## Outputs

```json
{
  "results": [
    {
      "text": "string",
      "score": 0.85,
      "lead_id": "string",
      "qdrant_similarity": 0.9,
      "recency_score": 0.8,
      "campaign_match_score": 1.0
    }
  ]
}
```

## Collections

| Collection | Purpose |
|------------|---------|
| `emails` | Past sent emails |
| `replies` | Received replies |
| `campaigns` | Campaign summaries |
| `signals` | Signal intelligence |
| `leads` | Lead profiles |
| `company_research` | Research documents |

## Tools Allowed

| Tool | Purpose | Config |
|------|---------|--------|
| `qdrant_search` | Semantic vector search | Qdrant client |

## Memory Access

| Memory Store | Permission | Usage |
|--------------|------------|-------|
| `campaign_memory` | read | Campaign type matching |
| `lead_memory` | read | Historical context |

## Ranking Formula

```
final_score = (similarity * 0.5) + (recency * 0.3) + (campaign_match * 0.2)
```

Where:
- **similarity**: Qdrant cosine similarity (0-1)
- **recency**: Exponential decay `exp(-0.01 * days_elapsed)`
- **campaign_match**: 1.0 if same campaign, 0.5 if same tone, 0.0 otherwise

## Constraints

- Maximum 10 results per query
- Minimum score threshold: 0.3
- Results sorted by final_score descending

## Success Criteria

- Returns results sorted by relevance
- Recency and campaign match factored in
- Text content extractable

## Escalation Rules

| Condition | Action |
|-----------|--------|
| Collection doesn't exist | Return empty results |
| No results found | Return empty array |
| Qdrant connection error | Return error with fallback |

## Example Invocation

```yaml
agent: rag_agent
input:
  query: "professional tone SaaS outreach successful reply"
  collection: "emails"
  limit: 3
  current_campaign_id: "camp_123"
```