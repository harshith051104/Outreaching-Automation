# LinkedIn Update Relationship Skill

## Purpose

Update the relationship stage for a LinkedIn contact in the database, maintaining a complete history of stage transitions.

## Inputs

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `user_id` | str | Yes | Current user ID |
| `linkedin_url` | str | Yes | Contact's LinkedIn URL |
| `new_stage` | str | Yes | New relationship stage |
| `lead_id` | str | No | Existing lead ID |
| `metadata` | dict | No | Additional context |

## Outputs

```json
{
  "success": true,
  "previous_stage": "connection_sent",
  "current_stage": "connection_accepted",
  "transition_recorded": true
}
```

## Execution Steps

- Query existing relationship from linkedin_relationships
- Record stage transition with timestamp in history array
- Update current stage
- If lead_id provided, also update lead status in leads collection
- Record tracking event in tracking_events collection
- Return transition result

## Relationship Stages

- `profile_viewed`
- `connection_sent`
- `connection_accepted`
- `message_sent`
- `replied`
- `followup_sent`
- `meeting_booked`
- `opportunity_created`
- `closed_won`
- `closed_lost`

## Validation Rules

- Stage must be one of the defined stages
- Transitions should follow logical order
- Timestamp must be recorded for each transition

## Failure Handling

| Error | Action |
|-------|--------|
| Relationship not found | Create new relationship record |
| Invalid stage | Reject with error message |
| DB write fails | Retry once |

## Integration

- **Database**: `linkedin_relationships` collection
- **Analytics**: Records events in `tracking_events` (existing)
- **Action**: `linkedin_update_relationship`
