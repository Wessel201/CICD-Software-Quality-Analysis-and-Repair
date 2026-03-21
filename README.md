# CICD-Software-Quality-Analysis-and-Repair

For backend run instructions (Docker + local `.venv`), see `app/api/README.md`.

## Backend (FastAPI) - first iteration

This repository now exposes a jobs-first FastAPI contract:

- `POST /api/v1/jobs` to create an analysis/repair job from either `github_url` or an uploaded archive referenced by `s3_key`
- `GET /api/v1/jobs/{job_id}` to retrieve job status and progress
- `GET /api/v1/jobs/{job_id}/results` to retrieve before/after findings and patch references
- `GET /api/v1/jobs/{job_id}/artifacts` to retrieve artifact metadata for the job
- `GET /api/v1/jobs/{job_id}/artifacts/{artifact_id}/download` to download a specific artifact file
- `POST /api/v1/jobs/{job_id}/repair` to trigger repair when a job is `READY_FOR_REPAIR`

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

The jobs API is now a submission and status layer only.

- `app/api` stores job metadata and submits work to SQS.
- `app/worker` is the only component that fetches source code, runs analysis, and performs repair.
- GitHub repositories are no longer cloned on the API host during job creation.

For async execution, run the API and worker with shared database access plus the SQS/S3/AWS environment needed by the worker pipeline.

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

## Terraform deployment note

The RDS PostgreSQL version is configurable with `db_engine_version` in Terraform.

- Default is `16`, which tells AWS to use the latest supported PostgreSQL 16.x minor version in the target region.
- Override when needed, for example: `terraform -chdir=terraform apply -var="db_engine_version=16.6"`.

If AWS returns an engine version availability error, list currently supported versions in your region and pick one:

`aws rds describe-db-engine-versions --engine postgres --region eu-central-1 --query 'DBEngineVersions[*].EngineVersion' --output text`

### Remote Terraform state for CI/CD

CI deploy and destroy workflows are configured to use an S3 backend with DynamoDB locking.

Required GitHub secrets:

- `TF_STATE_BUCKET`: S3 bucket name that stores Terraform state
- `TF_LOCK_TABLE`: DynamoDB table name used for Terraform state locking
- `DB_PASSWORD`: database password passed to Terraform as `TF_VAR_db_password`
- `OPENAI_API_KEY`: worker key passed to Terraform as `TF_VAR_openai_api_key`
- `API_KEY`: backend API key passed to Terraform as `TF_VAR_api_key`
- `VERCEL_TOKEN`: token used to manage Vercel project environment variables
- `VERCEL_ORG_ID`: Vercel team/user ID used by API calls (`teamId`)
- `VERCEL_PROJECT_ID`: Vercel project ID where env vars are updated

State key used by workflows:

- `prod/terraform.tfstate`

One-time bootstrap (create before first pipeline run):

1. Create an S3 bucket in `eu-central-1` for Terraform state.
2. Enable bucket versioning.
3. Create a DynamoDB table for locks with primary key `LockID` (string).
4. Add `TF_STATE_BUCKET` and `TF_LOCK_TABLE` in repository GitHub secrets.

Deployment pipeline behavior:

- After `terraform apply`, CI reads `alb_dns_name` from Terraform outputs.
- CI sets Vercel production env `API_BASE` to `http://<alb_dns_name>`.
- CI also sets Vercel production env `API_KEY` from GitHub Secret `API_KEY`.

Alternative bootstrap path:

1. Run the GitHub Actions workflow `Bootstrap Terraform Backend`.
2. Provide bucket and table names in the workflow inputs.
3. Add the same values to GitHub secrets `TF_STATE_BUCKET` and `TF_LOCK_TABLE`.
