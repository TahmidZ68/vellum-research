# API Reference Summary

Base URL: `/api/v1` (Interactive OpenAPI docs available at `/docs`).

## Authentication & Settings
- `POST /api/v1/auth/register` — Register a user and receive a JWT access token.
- `POST /api/v1/auth/login` — Authenticate with email/password.
- `GET /api/v1/auth/me` — Fetch current authenticated user profile.
- `GET /api/v1/settings` — Fetch user preferences, server-side provider diagnostics (no secrets), and 24h usage counts.
- `PATCH /api/v1/settings` — Update `full_name`, `preferred_language`, or `preferred_theme`.

## Projects
- `GET /api/v1/projects` — List user's projects (`?include_archived=true|false`).
- `POST /api/v1/projects` — Create a research project.
- `GET /api/v1/projects/{project_id}` — Fetch project details.
- `GET /api/v1/projects/{project_id}/runs` — List research runs inside a project.
- `PATCH /api/v1/projects/{project_id}` — Rename, update description, or archive/unarchive.
- `DELETE /api/v1/projects/{project_id}` — Delete project and cascaded runs/reports.

## Research Lifecycle
- `GET /api/v1/research` — List user's recent research runs.
- `POST /api/v1/research` — Start a new research investigation.
- `GET /api/v1/research/{run_id}` — Get run status, stage, counts, and research plan.
- `POST /api/v1/research/{run_id}/cancel` — Request graceful cancellation.
- `GET /api/v1/research/{run_id}/events` — Subscribe to real-time SSE progress events.
- `GET /api/v1/research/{run_id}/sources` — List collected sources and extraction status.
- `GET /api/v1/research/{run_id}/evidence` — List extracted claims and excerpts.
- `GET /api/v1/research/{run_id}/report` — Fetch latest report snapshot and linked citations.
- `GET /api/v1/research/{run_id}/messages` — List follow-up Q&A history.
- `POST /api/v1/research/{run_id}/follow-up` — Ask a follow-up question grounded in run evidence.
- `GET /api/v1/research/{run_id}/export?format=markdown|pdf` — Download report as Markdown or PDF.
