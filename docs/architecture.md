# Architecture — Vellum Research

Vellum Research uses a decoupled monorepo architecture designed for traceability, security, and horizontal scalability.

## Components

1. **Frontend (`frontend/`)**:
   - React 18 + TypeScript + Vite + Tailwind CSS.
   - Communicates exclusively with `/api/v1/*` endpoints using short-lived JWT Bearer tokens.
   - Subscribes to Server-Sent Events (`/api/v1/research/{run_id}/events`) for real-time stage updates.
2. **Backend API (`backend/app/main.py`)**:
   - FastAPI async application serving auth, project management, research lifecycle, SSE event streaming, follow-up Q&A, and Markdown/PDF exports.
   - Enforces ownership checks at the database query layer on every endpoint.
3. **Background Worker (`backend/app/workers/arq_worker.py`)**:
   - Consumes `run_research_job` tasks from Redis via ARQ in production/Docker Compose.
   - Falls back cleanly to `TASK_QUEUE_MODE=inline` for single-process local development and automated tests.
4. **Research Engine (`backend/app/agents/`)**:
   - Controlled 14-node LangGraph `StateGraph` with typed `ResearchState` and checkpointing.
   - Uses pluggable `BaseSearchProvider` and `BaseLLMProvider` interfaces.
5. **Persistence (`PostgreSQL` + `Alembic`)**:
   - Stores `users`, `research_projects`, `research_runs`, `research_plans`, `sources`, `evidence`, `reports` (versioned snapshots), `report_citations`, and `research_messages`.
