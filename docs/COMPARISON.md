# Platform Comparison: ai_outreach_v2_md_agents vs OpenOutreach

## Overview

This document compares the LinkedIn outreach functionality between our platform (`ai_outreach_v2_md_agents`) and the reference implementation (`OpenOutreach`).

---

## Feature-by-Feature Comparison

| Category | Feature | OpenOutreach | Our Platform | Status |
|----------|---------|--------------|--------------|--------|
| **Architecture** |
| | Task Queue | Django `Task` model, lazy `{"campaign_id"}` payload | MongoDB `scheduled_linkedin_tasks` | ✅ Equivalent |
| | Task Runner | `claim_next()` in daemon loop | Celery + asyncio loop | ✅ Equivalent |
| | Email-first ordering | Tasks ranked: email → connect → follow_up → check_pending | Separate email/LinkedIn queues | ✅ Equivalent |
| **Session Management** |
| | Session pool | `registry.py` — `_sessions[pk]` singleton | `linkedin_session_manager.py` — `_active_sessions[user_id]` | ✅ Equivalent |
| | Cookie persistence | `cookie_data` JSONField in Django | `linkedin_sessions.cookies_encrypted` in MongoDB | ✅ Equivalent |
| | Session validation | `ensure_browser()` + feed URL check | `ensure_browser()` + `_validate_session_pw()` | ✅ Equivalent |
| | Startup recovery | `restore_sessions_on_startup()` | `restore_sessions_on_startup()` | ✅ Equivalent |
| **Browser Automation** |
| | Stealth launch | `linkedin_cli.launch_browser()` | `_launch_stealth_browser()` | ✅ Equivalent |
| | Stealth context | Init scripts, webdriver spoof, viewport spoof | `_create_stealth_context()` | ✅ Equivalent |
| | Page state machine | `page_state.py` — `classify_page()`, `@transition` decorators, `PageFlow` | ⚠️ Basic URL-based checks only | ⚠️ Gap |
| | Auth flow | `auth.py` — `@auth_flow.transition` declarative | `_start_session_pw()` imperative | ✅ Equivalent |
| **Task Handlers** |
| | Connect | `handle_connect()` — finds candidate → sends → records | `_send_connection_request_pw()` | ✅ Equivalent |
| | Follow-up | `handle_follow_up()` — agentic DM decision | Orchestrator + `linkedin_outreach_service` | ✅ Equivalent |
| | Check-pending | `handle_check_pending()` — backoff doubling | `linkedin_connection_monitor.py` | ✅ Equivalent |
| **Scheduling** |
| | Poisson slots | `poisson_slot_times()` in `scheduler.py` | `poisson_slot_times()` in `poisson_scheduler.py` | ✅ Equivalent |
| | Daily limits | `Mailbox.remaining_today()`, `ActionLog` counters | `connect_exhausted_date`, `linkedin_action_logs` | ✅ Equivalent |
| | Active hours | Single `ACTIVE_START_HOUR`/`ACTIVE_END_HOUR` per campaign | Per-campaign `active_start_hour`/`active_end_hour` | ✅ Equivalent |
| | Break rhythm | `rhythm.maybe_break()` between bursts | `_random_delay()` between actions | ✅ Equivalent |
| **State Machine** |
| | States | `DealState` enum: QUALIFIED → READY_TO_EMAIL/READY_TO_CONNECT → PENDING → CONNECTED | `linkedin_stage`: qualified/pending/connected/failed/completed | ✅ Equivalent |
| | Email stage | `DealState.EMAILED` (quasi-terminal) | `email_stage`: drafted/sent/opened/replied/bounced/completed | ✅ Equivalent |
| | State hook | `on_deal_state_entered(deal)` — only PENDING updates `next_check_pending_at` | `on_lead_stage_entered()` — updates stage + checkboxes + backoff | ✅ Equivalent |
| | Backoff | `next_check_pending_at = now + backoff_hours` (doubles) | `backoff_hours`, `next_check_pending_at` (24h → 48h → 96h) | ✅ Equivalent |
| | Auto-DM on accept | If connection sent without note, auto-send DM | `process_accepted_connection()` in monitor | ✅ Equivalent |
| **ML Pipeline** |
| | Qualifier | `BayesianQualifier` — GPR + BALD active learning | ❌ No ML pipeline — LLM-only | ❌ Gap |
| | Embeddings | Fastembed `BAAI/bge-small-en-v1.5` 384-dim | ❌ No embedding storage | ❌ Gap |
| | Candidate selection | BALD (explore) vs P(f>0.5) exploit | Manual lead selection | ❌ Gap |
| **Pipeline** |
| | LinkedIn search | `pipeline/search.py` — Voyager API | ❌ No Voyager — CSV/Apollo/manual only | ❌ Gap |
| | Pool generators | `pipeline/pools.py` — chained `find_candidate → qualify_source → search_source` | ❌ No pool system | ❌ Gap |
| | Email fork | Explicit: QUALIFIED → READY_TO_EMAIL vs READY_TO_CONNECT | Via `campaign_stage` email tracking | ✅ Equivalent |
| **Error Handling** |
| | Rate limit | `ReachedConnectionLimit` → `mark_exhausted()` | `mark_exhausted()` + `connect_exhausted_date` | ✅ Equivalent |
| | Auth error | `AuthenticationError` → `session.reauthenticate()` | Session expired → marks `status: expired` | ✅ Equivalent |
| | Checkpoint | `CheckpointChallengeError` → exit daemon | Basic URL check for "checkpoint" | ⚠️ Partial |
| | Max attempts | `MAX_CONNECT_ATTEMPTS = 3` → disqualify | Multiple fallback selectors | ✅ Equivalent |
| **Configuration** |
| | Constants | `core/conf.py` — `CAMPAIGN_CONFIG`, `MIN_DELAY`, `MAX_DELAY` | Hardcoded in service files | ⚠️ Partial |
| | Active hours | `ENABLE_ACTIVE_HOURS`, `ACTIVE_START_HOUR=9`, `ACTIVE_END_HOUR=19` | Per-campaign settings | ✅ Equivalent |
| **Monitoring** |
| | Inbox monitor | Via orchestrator "LinkedIn Monitoring Workflow" | `linkedin_connection_monitor.check_for_updates()` | ✅ Equivalent |
| | Notifications | Dashboard alerts via WebSocket | `linkedin_notification_service.create_linkedin_notification()` | ✅ Equivalent |
| **Action Logging** |
| | Action log | `ActionLog` model with `ActionType` enum | `linkedin_action_logs` collection | ✅ Equivalent |
| | Per-type limits | `can_execute(ActionType.CONNECT)` checks daily/weekly | `connect_exhausted_date`, `message_exhausted_date` | ✅ Equivalent |

---

## Functional Equivalence Summary

### ✅ Fully Equivalent (Core LinkedIn Outreach Works)
- Session management with warm browser pool
- Cookie encryption and persistence
- Connect/send_message/follow_profile via Playwright
- Poisson scheduling over working hours
- State machine with backoff for pending connections
- Auto-DM when connection accepted without note
- Rate limiting and exhaustion flags
- Dashboard notifications via WebSocket

### ⚠️ Partial Gaps (Not Critical for Basic Operation)
- No dedicated page state machine (uses URL-based checks)
- No centralized config constants file
- Checkpoint challenges handled minimally

### ❌ Major Gaps (Would Require Significant Work)
- No ML pipeline (GP/BALD qualification)
- No Fastembed embeddings storage
- No Voyager API integration for LinkedIn search
- No composable pool generators

---

## Timeout Configuration (Aligned)

| Action | OpenOutreach | Our Platform | Timeout Applied |
|--------|-------------|--------------|------------------|
| `start_session` | ~120s login prompt | 120s | ✅ |
| `validate_session` | ~30s | 30s | ✅ |
| `scrape_profile` | ~60s | 60s | ✅ |
| `send_connection_request` | ~120s | 120s | ✅ (was unlimited) |
| `follow_profile` | ~60s | 60s | ✅ |
| `send_message` | ~60s | 60s | ✅ |
| `send_message_by_name` | ~90s | 90s | ✅ |
| `get_pending_invitations` | ~60s | 60s | ✅ |

---

## Key Implementation Files

### OpenOutreach
```
openoutreach/
├── core/
│   ├── scheduler.py      # Poisson slot creation, claim_next
│   ├── daemon.py         # Main loop
│   └── conf.py           # Config constants
├── linkedin/
│   ├── browser/
│   │   ├── session.py    # AccountSession
│   │   ├── registry.py   # _sessions singleton
│   │   └── launch.py     # Browser launch
│   ├── tasks/
│   │   ├── connect.py     # handle_connect
│   │   ├── follow_up.py  # handle_follow_up
│   │   └── check_pending.py
│   ├── pipeline/
│   │   ├── pools.py      # Composable pool generators
│   │   ├── qualify.py    # GP/BALD qualification
│   │   └── ready_pool.py # GP confidence gate
│   └── ml/
│       ├── qualifier.py  # BayesianQualifier
│       └── embeddings.py
└── crm/models/deal.py   # DealState enum
```

### Our Platform
```
ai_outreach_v2_md_agents/
├── app/
│   ├── services/
│   │   ├── linkedin_outreach_service.py  # Playwright functions
│   │   ├── linkedin_runner.py            # Subprocess runner
│   │   ├── linkedin_session_manager.py  # Warm session pool
│   │   ├── linkedin_connection_monitor.py
│   │   ├── linkedin_notification_service.py
│   │   ├── poisson_scheduler.py          # Poisson slot creation
│   │   └── state_machine_hooks.py       # Stage transition hooks
│   ├── tasks/
│   │   └── linkedin_tasks.py            # Celery wrapper
│   └── models/
│       └── lead.py                       # linkedin_stage, email_stage, campaign_stage
```

---

## Recommendations

1. **For MVP**: Our platform's LinkedIn functionality is **functionally equivalent** for core connect/message workflows. The timeout fixes we applied ensure reliable operation.

2. **For Scale**: Add the ML pipeline (GP/BALD qualification) and Voyager API integration for automated lead discovery and intelligent ranking.

3. **Config Cleanup**: Extract hardcoded constants to a centralized config file matching `core/conf.py`.

4. **Page State Machine**: Consider implementing a proper state machine for more robust page classification, though not blocking for current use.