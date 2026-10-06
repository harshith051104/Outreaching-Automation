# Tasks & Suggestions App (Standalone Module)

This directory contains the isolated Tasks and Suggestions modules extracted from the main web application.

## Folder Structure

```
tasks_and_suggestions_app/
├── frontend/
│   ├── pages/
│   │   ├── tasks/
│   │   │   ├── page.tsx               # Kanban & List view for tasks
│   │   │   └── [id]/page.tsx          # Task detail & activity view
│   │   └── suggestions/
│   │       ├── page.tsx               # AI Suggestions overview
│   │       └── [id]/page.tsx          # Suggestion details & approval flow
│   ├── services/
│   │   ├── task-api.ts                # Task API service methods
│   │   └── suggestion-api.ts          # Suggestion API service methods
│   └── components/
│       └── SuggestionMetrics.tsx      # Suggestion metrics visualization component
└── backend/
    ├── api/
    │   ├── suggestion_routes.py       # FastAPI routes for AI suggestions
    │   └── task_tracker_dashboard.py  # FastAPI routes for task tracking
    ├── services/
    │   ├── suggestion_ai_service.py   # AI suggestion generation logic
    │   └── task_scheduler_service.py  # Automated task scheduling service
    ├── models/
    │   └── suggestion.py              # MongoDB suggestion models
    └── schemas/
        └── task_tracker.py            # Task schemas & Pydantic models
```

## Setup & Integration

To integrate or run this standalone module:
1. **Frontend**: Import the pages and components into your target Next.js application or standalone router.
2. **Backend**: Register `suggestion_routes.py` and `task_tracker_dashboard.py` in your FastAPI `APIRouter`.
