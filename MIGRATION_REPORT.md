# AI Outreach Platform Migration Report

## Migration: CrewAI/Agno → Metadata-Driven Agent Architecture

**Date:** 2026-05-31
**Project:** ai_outreach_v2_md_agents
**Goal:** Functionally identical clone using modern metadata-driven agent architecture

---

## Executive Summary

This document maps every component from the existing CrewAI/Agno-based AI Outreach Platform to its equivalent in the new metadata-driven architecture. The new system preserves 100% of existing functionality while replacing hardcoded agent classes with declarative markdown-based agent definitions.

---

## Component Mapping

### 1. AGENTS

| Old Implementation | Type | New Implementation | File |
|---|---|---|---|
| `research_agent.py` - Research Agent | CrewAI Agent | `lead_discovery.md` | `/agents/lead_discovery.md` |
| `agno_agents.py` - Lead Discovery Agent | Agno Agent | `lead_discovery.md` | `/agents/lead_discovery.md` |
| `agno_agents.py` - Signal Intelligence Agent | Agno Agent | `signal_intelligence.md` | `/agents/signal_intelligence.md` |
| `agno_agents.py` - Opportunity Intelligence Agent | Agno Agent | `opportunity_agent.md` | `/agents/opportunity_agent.md` |
| `agno_agents.py` - Research Agent (web) | Agno Agent | `research_agent.md` | `/agents/research_agent.md` |
| `agno_agents.py` - RAG Agent | Agno Agent | `rag_agent.md` | `/agents/rag_agent.md` |
| `agno_agents.py` - Enrichment Agent | Agno Agent | `enrichment_agent.md` | `/agents/enrichment_agent.md` |
| `agno_agents.py` - Investor Discovery Agent | Agno Agent | `investor_discovery.md` | `/agents/investor_discovery.md` |
| `personalization_agent.py` - Personalization Agent | CrewAI Agent | `personalization_agent.md` | `/agents/personalization_agent.md` |
| `outreach_writer_agent.py` - Outreach Writer Agent | CrewAI Agent | `email_writer.md` | `/agents/email_writer.md` |
| `reply_classification_agent.py` - Reply Classification Agent | CrewAI Agent | `reply_monitor_agent.md` | `/agents/reply_monitor_agent.md` |
| `followup_agent.py` - Follow-up Agent | CrewAI Agent | `followup_agent.md` | `/agents/followup_agent.md` |
| `analytics_agent.py` - Analytics Agent | CrewAI Agent | `analytics_agent.md` | `/agents/analytics_agent.md` |
| `tracking_agent.py` - Tracking Agent | CrewAI Agent | `analytics_agent.md` | `/agents/analytics_agent.md` |
| `content_strategy_agent.py` - Content Strategy Agent | CrewAI Agent | `campaign_strategist.md` | `/agents/campaign_strategist.md` |

### 2. CREWS (Orchestration)

| Old Implementation | Type | New Implementation | File |
|---|---|---|---|
| `OutreachCrew` | CrewAI Crew | `campaign_execution.yaml` | `/workflows/campaign_execution.yaml` |
| `ReplyProcessingCrew` | CrewAI Crew | `reply_monitoring.yaml` | `/workflows/reply_monitoring.yaml` |
| `FollowupCrew` | CrewAI Crew | `followup_generation.yaml` | `/workflows/followup_generation.yaml` |
| `AnalyticsCrew` | CrewAI Crew | `analytics_learning.yaml` | `/workflows/analytics_learning.yaml` |

### 3. TASKS / BACKGROUND JOBS

| Old Implementation | Trigger | New Implementation | File |
|---|---|---|---|
| `execute_campaign` | Manual/Celery | `campaign_execution.yaml` + `orchestrator/engine.py` | `/workflows/campaign_execution.yaml` |
| `process_pending_followups` | Celery Beat (1 min) | `followup_tasks.py` | `/app/tasks/followup_tasks.py` |
| `refresh_all_campaign_analytics` | Celery Beat (15 min) | `analytics_tasks.py` | `/app/tasks/analytics_tasks.py` |
| `poll_gmail_replies` | Celery Beat (5 min) | `reply_monitoring.yaml` | `/workflows/reply_monitoring.yaml` |
| `_campaign_processor_loop()` | Async loop (30 sec) | `orchestrator/engine.py` | `/orchestrator/engine.py` |

### 4. TOOLS / INTEGRATIONS

| Old Implementation | Service | New Implementation | File |
|---|---|---|---|
| `WebSearchTool` | DuckDuckGo + Groq | `web_scraping.md` skill | `/skills/web_scraping.md` |
| `EmailAnalysisTool` | Internal | `email_generation.md` skill | `/skills/email_generation.md` |
| `CampaignMetricsTool` | Internal | `campaign_analysis.md` skill | `/skills/campaign_analysis.md` |
| `ApolloService` | Apollo.io API | `apollo_search.md` skill | `/skills/apollo_search.md` |
| `HunterEnrichmentService` | Hunter.io API | `hunter_verification.md` skill | `/skills/hunter_verification.md` |
| `TavilyService` | Tavily API | `signal_detection.md` skill | `/skills/signal_detection.md` |
| `FirecrawlService` | Firecrawl API | `web_scraping.md` skill | `/skills/web_scraping.md` |
| `GmailService` | Google Gmail API | Integrated in `gmail_service.py` | `/app/services/gmail_service.py` |
| `QdrantService` | Qdrant vector DB | `rag_retrieval.md` skill + `memory_registry.yaml` | `/skills/rag_retrieval.md` |

### 5. API ENDPOINTS

| Old Router | Prefix | New Implementation | File |
|---|---|---|---|
| `auth_routes.py` | `/api/auth` | `auth_routes.py` | `/app/api/auth_routes.py` |
| `campaign_routes.py` | `/api/campaigns` | `campaign_routes.py` | `/app/api/campaign_routes.py` |
| `lead_routes.py` | `/api/leads` | `lead_routes.py` | `/app/api/lead_routes.py` |
| `gmail_routes.py` | `/api/gmail` | `gmail_routes.py` | `/app/api/gmail_routes.py` |
| `analytics_routes.py` | `/api/analytics` | `analytics_routes.py` | `/app/api/analytics_routes.py` |
| `tracking_routes.py` | `/api/track` | `tracking_routes.py` | `/app/api/tracking_routes.py` |
| `crewai_routes.py` | `/api/ai` | `ai_routes.py` | `/app/api/ai_routes.py` |
| `followup_routes.py` | `/api/followups` | `followup_routes.py` | `/app/api/followup_routes.py` |
| `chatbot_routes.py` | `/api/chatbot` | `chatbot_routes.py` | `/app/api/chatbot_routes.py` |
| `reply_monitor_routes.py` | `/api/reply-monitor` | `reply_monitor_routes.py` | `/app/api/reply_monitor_routes.py` |
| `webhook_routes.py` | `/api/webhooks` | `webhook_routes.py` | `/app/api/webhook_routes.py` |
| `lead_management_routes.py` | `/api/lead-management` | `lead_management_routes.py` | `/app/api/lead_management_routes.py` |
| `chat_session_routes.py` | `/api/chat-sessions` | `chat_session_routes.py` | `/app/api/chat_session_routes.py` |
| `file_upload_routes.py` | `/api/file-upload` | `file_upload_routes.py` | `/app/api/file_upload_routes.py` |
| `discovery_routes.py` | `/api/discovery` | `discovery_routes.py` | `/app/api/discovery_routes.py` |
| `enrichment_routes.py` | `/api/enrichment` | `enrichment_routes.py` | `/app/api/enrichment_routes.py` |
| `signal_routes.py` | `/api/signals` | `signal_routes.py` | `/app/api/signal_routes.py` |
| `pitch_deck_routes.py` | `/api/pitch-deck` | `pitch_deck_routes.py` | `/app/api/pitch_deck_routes.py` |
| `linkedin_routes.py` | `/api/linkedin` | `linkedin_routes.py` | `/app/api/linkedin_routes.py` |

### 6. SERVICES

| Old Implementation | New Implementation | File |
|---|---|---|
| `campaign_service.py` | `campaign_service.py` | `/app/services/campaign_service.py` |
| `email_service.py` | `email_service.py` | `/app/services/email_service.py` |
| `followup_service.py` | `followup_service.py` | `/app/services/followup_service.py` |
| `analytics_service.py` | `analytics_service.py` | `/app/services/analytics_service.py` |
| `tracking_service.py` | `tracking_service.py` | `/app/services/tracking_service.py` |
| `memory_service.py` | `memory_service.py` | `/app/services/memory_service.py` |
| `reply_monitor_service.py` | `reply_monitor_service.py` | `/app/services/reply_monitor_service.py` |
| `chatbot_service.py` | `chatbot_service.py` | `/app/services/chatbot_service.py` |
| `signal_service.py` | `signal_service.py` | `/app/services/signal_service.py` |
| `lead_discovery_service.py` | `lead_discovery_service.py` | `/app/services/lead_discovery_service.py` |
| `task_scheduler_service.py` | `task_scheduler_service.py` | `/app/services/task_scheduler_service.py` |
| `webhook_service.py` | `webhook_service.py` | `/app/services/webhook_service.py` |
| `apollo_service.py` | `apollo_service.py` | `/app/services/apollo_service.py` |
| `hunter_enrichment_service.py` | `hunter_enrichment_service.py` | `/app/services/hunter_enrichment_service.py` |
| `tavily_service.py` | `tavily_service.py` | `/app/services/tavily_service.py` |
| `firecrawl_service.py` | `firecrawl_service.py` | `/app/services/firecrawl_service.py` |
| `gmail_service.py` | `gmail_service.py` | `/app/services/gmail_service.py` |
| `qdrant_service.py` | `qdrant_service.py` | `/app/services/qdrant_service.py` |

### 7. DATABASE COLLECTIONS (MongoDB)

| Collection | Purpose | Status |
|---|---|---|
| `users` | User accounts | Preserved |
| `campaigns` | Campaign documents | Preserved |
| `leads` | Lead contacts | Preserved |
| `emails` | Sent emails | Preserved |
| `tracking_events` | Open/click/reply events | Preserved |
| `followup_tasks` | Scheduled follow-ups | Preserved |
| `scheduled_tasks` | Multi-channel sequence tasks | Preserved |
| `replies` | Received replies | Preserved |
| `signals` | Signal intelligence | Preserved |
| `opportunities` | Opportunity evaluations | Preserved |
| `gmail_accounts` | Connected Gmail accounts | Preserved |
| `webhooks` | Webhook subscriptions | Preserved |
| `webhook_events` | Webhook delivery logs | Preserved |
| `analytics` | Cached campaign analytics | Preserved |
| `analytics_learning_memory` | AI-generated campaign insights | Preserved |
| `lead_memories` | Per-lead memory | Preserved |
| `campaign_memories` | Campaign-level memory | Preserved |
| `lead_lists` | Lead list groupings | Preserved |
| `block_list` | Blocked emails/domains | Preserved |
| `content` | LinkedIn content calendars | Preserved |
| `outreach` | Manual export queue | Preserved |

### 8. QDRANT COLLECTIONS

| Collection | Dimension | Purpose | Status |
|---|---|---|---|
| `campaigns` | 384 | Campaign embeddings | Preserved |
| `leads` | 384 | Lead profile embeddings | Preserved |
| `emails` | 384 | Sent email embeddings | Preserved |
| `replies` | 384 | Reply embeddings | Preserved |
| `company_research` | 384 | Company research embeddings | Preserved |
| `signals` | 384 | Signal intelligence embeddings | Preserved |

### 9. TRACKING MECHANISMS

| Old Implementation | New Implementation | Status |
|---|---|---|
| Pixel tracker (1x1 GIF) | `pixel_tracker.py` | Preserved |
| Click tracker (URL redirect) | `click_tracker.py` | Preserved |
| Reply tracker (Gmail thread analysis) | `tracking_service.py` | Preserved |

### 10. WEBSOCKET

| Old Implementation | New Implementation | File |
|---|---|---|
| `ConnectionManager` | `connection_manager.py` | `/app/websocket/connection_manager.py` |
| `broadcast_reply()` | `broadcast_reply()` | Preserved |
| `broadcast_draft_ready()` | `broadcast_draft_ready()` | Preserved |
| `broadcast_draft_sent()` | `broadcast_draft_sent()` | Preserved |

---

## New Architecture Components

### Agent Files (Markdown-based)

```
/agents/
├── lead_discovery.md        # Apollo/Tavily lead search
├── signal_intelligence.md  # Hiring/funding/tech signals
├── opportunity_agent.md     # Opportunity evaluation
├── research_agent.md        # Company/lead research
├── personalization_agent.md # Email personalization
├── email_writer.md          # Cold email generation
├── followup_agent.md        # Follow-up generation
├── reply_monitor_agent.md   # Reply classification
├── analytics_agent.md       # Campaign analytics
├── campaign_strategist.md   # Content strategy
├── enrichment_agent.md      # Email verification
├── rag_agent.md             # Vector retrieval
└── investor_discovery.md    # Investor search
```

### Skill Files (Markdown-based)

```
/skills/
├── apollo_search.md         # Apollo API integration
├── hunter_verification.md   # Hunter.io email verification
├── web_scraping.md          # Tavily/Firecrawl scraping
├── signal_detection.md       # Signal extraction
├── opportunity_scoring.md   # Opportunity scoring
├── email_generation.md       # Email writing with spam check
├── followup_generation.md   # Follow-up generation
├── reply_classification.md  # Reply intent classification
├── campaign_analysis.md    # Analytics computation
└── rag_retrieval.md         # Qdrant semantic search
```

### Workflow Files (YAML-based)

```
/workflows/
├── lead_discovery.yaml      # Lead search → enrichment → store
├── campaign_creation.yaml   # Campaign setup workflow
├── campaign_execution.yaml  # Research → personalize → write → send
├── reply_monitoring.yaml    # Poll → classify → notify
├── followup_generation.yaml # Generate → approve → send
└── analytics_learning.yaml  # Analyze → compare → store learnings
```

### Tool Registry

```
/tools/
├── tools.yaml               # All tool definitions with schemas
├── apollo_tool.py
├── hunter_tool.py
├── tavily_tool.py
├── firecrawl_tool.py
├── gmail_tool.py
├── qdrant_tool.py
└── email_tool.py
```

### Memory Registry

```
/memory/
├── memory_registry.yaml     # Memory stores and agent permissions
```

---

## Key Differences from Old Architecture

### Old (CrewAI/Agno)
- Agents defined as Python classes
- Tasks defined as Python Task objects
- Crews defined as Python class compositions
- Hardcoded tool bindings
- Code changes required to add new agents

### New (Metadata-Driven)
- Agents defined as Markdown files with YAML frontmatter
- Skills defined as reusable Markdown components
- Workflows defined as declarative YAML
- Dynamic tool loading from registry
- New agents added by creating markdown files only

---

## Orchestrator Design

The new orchestrator (`/orchestrator/engine.py`) is configuration-driven:

1. **Agent Loader**: Reads `agents/*.md`, parses YAML frontmatter, instantiates agent configs
2. **Skill Loader**: Reads `skills/*.md`, builds skill registry
3. **Workflow Loader**: Reads `workflows/*.yaml`, builds execution graphs
4. **Tool Registry**: Loads tools from `tools/tools.yaml`
5. **Memory Manager**: Connects to MongoDB + Qdrant, manages RAG retrieval
6. **Execution Engine**: Runs workflow steps, passes context between agents

---

## Feature Parity Checklist

- [x] Lead Discovery (Apollo → Tavily → Firecrawl fallback)
- [x] Lead Enrichment (Hunter verification)
- [x] Deliverability Checks (spam analysis)
- [x] Deduplication (lead_hash)
- [x] Signal Intelligence (Tavily + Firecrawl)
- [x] Opportunity Evaluation (LLM-based)
- [x] Campaign Generation (research → personalize → write)
- [x] Email Writing (with tone control)
- [x] Follow-Up Generation (sequence-aware)
- [x] Campaign Scheduling (multi-channel sequences)
- [x] Gmail Sending (OAuth2)
- [x] Tracking Pixel Logic
- [x] Open Tracking
- [x] Click Tracking
- [x] Reply Monitoring (Gmail polling)
- [x] Reply Classification (AI-based)
- [x] Analytics (dashboard + campaign)
- [x] Learning Memory (Qdrant + MongoDB)
- [x] Qdrant RAG (FastEmbed embeddings)
- [x] MongoDB Storage (all collections)
- [x] Dashboard APIs (all endpoints)
- [x] Background Scheduler (Celery Beat)
- [x] Async Processing (asyncio)

---

## Migration Status

**COMPLETE** - All 100% of existing functionality has been mapped to new architecture components.