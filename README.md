# AI Outreach Platform v2 - Metadata-Driven Architecture

## Overview

This is a complete migration of the AI Outreach Platform from CrewAI/Agno agent classes to a modern metadata-driven agent architecture.

## Architecture

### Old Architecture (CrewAI/Agno)
- Agents defined as Python classes
- Tasks defined as Task objects
- Crews as class compositions
- Hardcoded tool bindings
- Code changes needed to add agents

### New Architecture (Metadata-Driven)
- Agents defined as Markdown files with YAML frontmatter
- Skills as reusable Markdown components
- Workflows as declarative YAML
- Dynamic tool loading from registry
- New agents added via markdown files only

## Directory Structure

```
ai_outreach_v2_md_agents/
├── agents/              # Markdown agent definitions
│   ├── lead_discovery.md
│   ├── signal_intelligence.md
│   ├── opportunity_agent.md
│   ├── research_agent.md
│   ├── personalization_agent.md
│   ├── email_writer.md
│   ├── followup_agent.md
│   ├── reply_monitor_agent.md
│   ├── analytics_agent.md
│   ├── campaign_strategist.md
│   ├── enrichment_agent.md
│   ├── rag_agent.md
│   └── investor_discovery.md
├── skills/              # Reusable skill definitions
│   ├── apollo_search.md
│   ├── hunter_verification.md
│   ├── web_scraping.md
│   ├── signal_detection.md
│   ├── opportunity_scoring.md
│   ├── email_generation.md
│   ├── followup_generation.md
│   ├── reply_classification.md
│   ├── campaign_analysis.md
│   └── rag_retrieval.md
├── workflows/           # Workflow YAML definitions
│   ├── lead_discovery.yaml
│   ├── campaign_creation.yaml
│   ├── campaign_execution.yaml
│   ├── reply_monitoring.yaml
│   ├── followup_generation.yaml
│   └── analytics_learning.yaml
├── tools/               # Tool registry
│   └── tools.yaml
├── memory/              # Memory registry
│   └── memory_registry.yaml
├── orchestrator/        # Orchestration engine
│   ├── engine.py
│   └── __init__.py
└── app/                # FastAPI application
    ├── main.py
    ├── api/
    ├── services/
    └── ...
```

## Key Concepts

### Agents
Each agent is defined in a markdown file with:
- **role**: Agent's purpose
- **objective**: What the agent aims to achieve
- **responsibilities**: List of duties
- **inputs/outputs**: Data schemas
- **tools_allowed**: Which tools the agent can use
- **memory_access**: Memory store permissions
- **decision_rules**: How the agent makes decisions
- **constraints**: Limitations and rules
- **success_criteria**: How success is measured
- **escalation_rules**: What to do when things go wrong

### Skills
Reusable capabilities defined as:
- **purpose**: What the skill does
- **inputs/outputs**: Data schemas
- **execution_steps**: How to execute
- **validation_rules**: What to validate
- **failure_handling**: How to handle failures

### Workflows
YAML definitions with:
- **execution order**: Steps in sequence
- **dependencies**: What each step needs
- **branching**: Conditional paths
- **retry logic**: How to retry on failure
- **failure handling**: What to do on errors
- **human approval checkpoints**: Where to pause for approval

## Running the Application

```bash
# Install dependencies
pip install -r requirements.txt

# Run FastAPI application
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# Run Celery worker (separate terminal)
celery -A celery_worker worker --loglevel=info
celery -A celery_worker beat --loglevel=info
```

## API Endpoints

### AI Endpoints
- `POST /api/ai/orchestrate` - Execute a metadata-driven workflow
- `POST /api/ai/generate-email` - Generate outreach email
- `POST /api/ai/classify-reply` - Classify email reply
- `GET /api/agents` - List available agents
- `GET /api/workflows` - List available workflows

## Adding New Agents

1. Create a new markdown file in `agents/`
2. Define the agent's configuration in YAML frontmatter
3. Add the agent name to relevant workflows
4. No code changes required

## Example Agent Definition

```markdown
---
name: my_new_agent
type: agent
role: My New Agent
version: 1.0.0
---

# My New Agent

## Identity

**Role:** My New Agent
**Purpose:** Description of what this agent does

## Objective

Describe the main objective here.

## Inputs/Outputs

Define schemas...

## Tools Allowed

List permitted tools...

## Memory Access

Define memory store permissions...

## Decision Rules

1. First rule...
2. Second rule...

## Success Criteria

- Criterion 1
- Criterion 2
```

## Migration Complete

All original functionality has been preserved:
- Lead Discovery (Apollo → Tavily → Firecrawl)
- Lead Enrichment (Hunter verification)
- Signal Intelligence (Tavily + Firecrawl)
- Opportunity Evaluation
- Campaign Execution (research → personalize → write → send)
- Email Tracking (pixel, click, reply)
- Reply Monitoring (Gmail polling)
- Analytics (dashboard + AI insights)
- Memory (Qdrant + MongoDB)
- Multi-channel Sequences (email, LinkedIn, call, task)
- Background Processing (Celery + async loops)
- All API endpoints preserved