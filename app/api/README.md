# API Backend README

This README explains how to run the backend API with either Docker (recommended) or a local Python `.venv`.

## What this API exposes

- `POST /api/v1/jobs`
- `GET /api/v1/jobs/{job_id}`
- `GET /api/v1/jobs/{job_id}/results`
- `GET /api/v1/jobs/{job_id}/artifacts`
- `GET /api/v1/jobs/{job_id}/artifacts/{artifact_id}/download`
- `POST /api/v1/jobs/{job_id}/repair`

Swagger UI: `http://localhost:8000/docs`

---

## Option 1: Run with Docker (recommended)

Use this option for the full stack (API + worker + Redis + Postgres).

### Prerequisites

- Docker Desktop running

### Start

From repository root:

```bash
docker compose up --build -d
```

Or with helper script:

```bash
./exe.sh up
```

### Check status/logs

```bash
docker compose ps
docker compose logs -f api
docker compose logs -f worker
```

### Stop

```bash
docker compose down
```

---

## Option 2: Run locally with `.venv`

Use this option when developing quickly without containers.

### Prerequisites

- Python 3.12+ (project tested on 3.13)
- Git

### Setup virtual environment

From `app/api`:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dev.txt
```

### Database migration

Run from `app/api`:

```powershell
alembic -c alembic.ini upgrade head
```

### Run API only (eager mode)

```powershell
$env:CELERY_TASK_ALWAYS_EAGER="true"
uvicorn app.main:app --reload
```

### Run API + async worker locally

1. Start Redis (local or Docker)
2. Start API terminal:

```powershell
$env:CELERY_TASK_ALWAYS_EAGER="false"
$env:CELERY_BROKER_URL="redis://localhost:6379/0"
$env:CELERY_RESULT_BACKEND="redis://localhost:6379/0"
uvicorn app.main:app --reload
```

3. Start worker in second terminal:

```powershell
$env:CELERY_TASK_ALWAYS_EAGER="false"
$env:CELERY_BROKER_URL="redis://localhost:6379/0"
$env:CELERY_RESULT_BACKEND="redis://localhost:6379/0"
celery -A app.celery_app:celery_app worker --loglevel=info
```

---

## Quick test

From `app/api`:

```powershell
pytest -q
```

---

## Notes

- Artifact JSON files are written under `app/api/uploads/<job_id>/artifacts/...`.
- In Docker, this storage is mounted via the `uploads_data` volume.
