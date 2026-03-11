# QC Worker - Development Guide

This worker is the core engine for Scenario 2 (Pipeline).

## Getting Started

1.  **Environment Setup**:
    - Create a `.env` file in the root directory.
    - Add your `UVALLM_API_KEY`.

2.  **Deployment**:
    Run the following command to start the worker:
    ```bash
    docker-compose up --build
    ```

## TODOs for Cloud/API Teams

### Cloud Interaction
- [ ] **S3 Integration**: Currently, the worker scans the local filesystem mapped via Docker volume (`/src`). For production, we need logic to pull repositories from S3 or directly from GitHub via the API.
- [ ] **Deployment**: The `terraform/` directory should be updated to deploy the worker as a task (e.g., AWS ECS or Lambda) if not using EC2 directly.

### API Integration
- [ ] **Job Queue**: The worker currently runs a single analysis. We should implement a message queue (e.g., Redis or AWS SQS) so the API can push "analysis jobs" and the worker can process them asynchronously.
- [ ] **Webhook**: Integrate GitHub webhooks to trigger the worker on `push` events.

### Verification & Git
- [ ] **Git Push**: Logic to create a new branch and push fixes is drafted but needs GitHub token configuration (`GITHUB_TOKEN`).
- [ ] **Unit Tests**: The worker needs to be able to run `pytest` or similar if the repository provides them.
