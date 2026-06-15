# RAG Retrieval Skill

## Purpose

Query Qdrant vector store for semantic similarity search across emails, replies, campaigns, and signals.

## Inputs

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `collection` | str | Yes | Collection to search |
| `query` | str | Yes | Semantic search query |
| `limit` | int | No | Max results (default: 3) |
| `current_campaign_id` | str | No | For campaign match boost |

## Collections

| Collection | Dimension | Purpose |
|------------|-----------|---------|
| emails | 384 | Sent email embeddings |
| replies | 384 | Reply embeddings |
| campaigns | 384 | Campaign summaries |
| signals | 384 | Signal intelligence |
| leads | 384 | Lead profiles |
| company_research | 384 | Research docs |

## Outputs

```json
{
  "results": [
    {
      "text": "string",
      "score": 0.85,
      "lead_id": "string",
      "entity_id": "string",
      "qdrant_similarity": 0.9,
      "recency_score": 0.8,
      "campaign_match_score": 1.0
    }
  ]
}
```

## Execution Steps

1. Search Qdrant for similar documents
2. Load current campaign for type matching
3. Apply ranking formula
4. Return sorted results

## Ranking Formula

```
final_score = (similarity * 0.5) + (recency_score * 0.3) + (campaign_match * 0.2)
```

### Similarity Component (0.5 weight)

Qdrant cosine similarity score (0-1)

### Recency Component (0.3 weight)

Exponential decay: `exp(-0.01 * days_elapsed)`

### Campaign Match Component (0.2 weight)

| Condition | Score |
|-----------|-------|
| Same campaign | 1.0 |
| Same tone | 0.5 |
| Different | 0.0 |

## Embedding Model

- **Model**: `BAAI/bge-small-en-v1.5`
- **Dimension**: 384
- **Library**: FastEmbed

## Validation Rules

- Collection must exist
- Query must be non-empty
- Limit must be 1-100

## Failure Handling

| Error | Action |
|-------|--------|
| Collection missing | Create collection |
| No results | Return empty array |
| Qdrant error | Return error with fallback |

## Examples

```python
results = await search_similar(
    collection="emails",
    query="professional SaaS outreach successful reply",
    limit=3,
    current_campaign_id="camp_123"
)
```

## Integration

- **Service**: `qdrant_service.py`
- **Embedding**: FastEmbed
- **Storage**: Qdrant collections