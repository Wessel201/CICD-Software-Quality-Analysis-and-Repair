# CICD-Software-Quality-Analysis-and-Repair

For backend run instructions (Docker + local `.venv`), see `app/api/README.md`.

## Backend (FastAPI) - first iteration

This repository now exposes a jobs-first FastAPI contract:

- `POST /api/v1/jobs` to create an analysis/repair job from either `github_url` or an uploaded `file`
- `GET /api/v1/jobs/{job_id}` to retrieve job status and progress
- `GET /api/v1/jobs/{job_id}/results` to retrieve before/after findings and patch references
- `GET /api/v1/jobs/{job_id}/artifacts` to retrieve artifact metadata for the job
- `GET /api/v1/jobs/{job_id}/artifacts/{artifact_id}/download` to download a specific artifact file
- `POST /api/v1/jobs/{job_id}/repair` to trigger repair when a job is `READY_FOR_REPAIR`

Job creation enforces a maximum repository size of `100 MB` for uploaded archives.

### Run locally

From `app/api`:

1. `pip install -r requirements.txt`
2. `uvicorn app.main:app --reload`

API docs are available at `http://127.0.0.1:8000/docs`.

### Run tests

From `app/api`:

1. `pip install -r requirements.txt -r requirements-dev.txt`
2. `pytest`

### Jobs pipeline execution

The jobs API now dispatches analysis and repair through Celery tasks.

- Default local mode uses `CELERY_TASK_ALWAYS_EAGER=true` so tasks run in-process (no Redis needed).
- For real async execution, run with `CELERY_TASK_ALWAYS_EAGER=false` and provide a broker.

Example (real async):

1. Start Redis (`redis://localhost:6379/0`)
2. In `app/api` run API:
   - `set CELERY_TASK_ALWAYS_EAGER=false`
   - `uvicorn app.main:app --reload`
3. In another terminal run worker:
   - `celery -A app.celery_app:celery_app worker --loglevel=info`

### Database and migrations

The jobs flow now uses a job-centric SQL database schema with repository-layer persistence.

- Default local DB: `sqlite:///./app.db`.
- Override DB URL with `DATABASE_URL` for PostgreSQL/managed cloud DB.

Run migrations from `app/api`:

1. `alembic -c alembic.ini upgrade head`

Then run API:

2. `uvicorn app.main:app --reload`

Optional: set `AUTO_INIT_DB=true` to auto-create schema from ORM metadata (dev-only fallback; migration-first is recommended).

Core tables:

- `repositories`
- `jobs`
- `analysis_runs`
- `findings`
- `artifacts`
