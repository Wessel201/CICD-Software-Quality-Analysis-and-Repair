# QC Worker - Development Guide

This worker is the async execution engine for Terraform-backed processing.

Production authority:
- Queue: `SQS_QUEUE_URL`
- Source/artifacts storage: `S3_BUCKET_NAME`
- Metadata/findings: PostgreSQL (`DATABASE_URL` or `DB_*` variables)

## Getting Started

1.  **Environment Setup**:
    - Create a `.env` file in the root directory.
    - Provide cloud/runtime variables:
      - `SQS_QUEUE_URL`
      - `S3_BUCKET_NAME`
      - `AWS_REGION` (defaults to `eu-central-1`)
      - `DATABASE_URL` or `DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_PORT`

2.  **Deployment**:
    Run the following command to start the worker:
    ```bash
    docker-compose up --build
    ```

3.  **Runtime Entry Point**:
    - Container default command is now:
    ```bash
    python main.py
    ```
    - `main.py` long-polls SQS and processes one message at a time.

## Current Processing Flow

1. Receive message from SQS (`job_id`, `action`, optional control fields)
2. Read repository/job context from shared PostgreSQL
3. Fetch source from GitHub or S3 upload archive
4. Run analyzers (Bandit, Pylint, Radon, TruffleHog)
5. Persist findings into `analysis_runs` + `findings`
6. Update job lifecycle status in `jobs`
7. Delete SQS message on success; keep on failure for retry/DLQ handling

## Local Single-File Run (No SQS/DB/S3)

Use the local runner to execute worker analysis/repair logic for one file directly:

```bash
cd app/worker
python run_local_file.py /absolute/path/to/file.py
```

Run with repair enabled (requires `OPENAI_API_KEY`; optional `REPAIR_MODEL`):

```bash
cd app/worker
OPENAI_API_KEY=... REPAIR_MODEL=deepseek-chat python run_local_file.py /absolute/path/to/file.py --repair --cycles 1
```

Write repaired result back to the original file:

```bash
cd app/worker
OPENAI_API_KEY=... python run_local_file.py /absolute/path/to/file.py --repair --in-place
```

`--in_place` is also accepted as an alias for `--in-place`.

Write JSON output to a file instead of stdout:

```bash
cd app/worker
python run_local_file.py /absolute/path/to/file.py --output /tmp/worker-local-result.json
```

## Remaining Work

### Cloud Interaction
- [x] S3/GitHub source retrieval implemented in worker runtime.
- [ ] Store generated artifacts/reports back to S3 with signed download support.

### API Integration
- [x] SQS-driven async job intake implemented.
- [ ] Remove deprecated local/Celery pathways once all environments are migrated.

### Verification & Git
- [ ] Implement actual repair transformations (currently repair phase re-analyzes unchanged source).
- [ ] Add test execution hooks (optional, repository-aware).
- [ ] Add structured observability and DLQ replay runbooks.
