# AGENTS.md

## Cursor Cloud specific instructions

### Architecture
This is a two-part application: Python FastAPI backend (under `src/`) + Next.js 16 frontend (under `frontend/`). See `README.md` for full architecture diagram and API endpoints reference.

### Infrastructure Services (Docker Compose)
Three infrastructure services must be running before starting the backend:
```bash
# Ensure Docker daemon is running, then:
docker compose up -d   # Starts Redis (6379), PostgreSQL (5433), Apache Fuseki (3030)
```
Check status: `docker ps` — all three should show `(healthy)`.

### Starting the Backend
Run DB migrations with `alembic upgrade head` from the repo root, then start the API server with `uvicorn synaptiq.api.app:app --reload --host 0.0.0.0 --port 8000`. Verify with a health check GET request to `/health` on port 8000. <!-- pragma: allowlist secret -->

### Starting the Frontend
From the `frontend/` directory, run `npm run dev` to start the Next.js dev server on port 3000.

### Gotchas and Non-Obvious Notes
- The Python package must be installed as editable (`pip install -e .`) for the main module to be importable. `requirements.txt` alone is not sufficient.
- `~/.local/bin` must be on `PATH` for `uvicorn`, `alembic`, `celery` CLI commands (pip installs there for non-root users).
- Pydantic Settings (`config/settings.py`) has **required fields** with no defaults for external service keys/URIs. A `.env` file with these values must exist at the repo root for the backend to start. Copy `.env.example` as a starting point and fill in all required values.
- The Docker Compose file has `version: '3.8'` which produces a deprecation warning — this is harmless.
- Frontend form input fields have a CSS styling issue (white text on near-white background on auth pages); this is a pre-existing UI bug.
- All API routes use the `/api/v1/` prefix. The Notes `content` field is block-based (list of dicts), not plain text.
- Celery worker (`celery -A synaptiq.workers.celery_app worker --loglevel=info`) is needed only for background ingestion tasks; the backend starts fine without it. <!-- pragma: allowlist secret -->
- The frontend API base URL defaults to the backend on port 8000 (hardcoded in `frontend/src/lib/api/`). Set `NEXT_PUBLIC_API_BASE_URL` env var to override.

### Lint / Test / Build
- **Frontend lint**: `cd frontend && npx eslint .` (pre-existing warnings/errors in the codebase)
- **Frontend build**: `cd frontend && npx next build`
- **Backend tests**: `pytest tests/ -v` (per README; no test directory exists yet)
- **Frontend tests**: None configured
