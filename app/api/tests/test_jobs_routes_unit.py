from datetime import datetime, timezone

from fastapi.testclient import TestClient

import app.api.routes.jobs as jobs_routes
from app.schemas.job import JobArtifactsResponse, JobCreateResponse, JobListResponse, JobStatus, JobStatusResponse, SourceFileResponse


client = TestClient(jobs_routes.router)


def _mount_client() -> TestClient:
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(jobs_routes.router, prefix="/api/v1/jobs")
    return TestClient(app)


def test_list_jobs_route(monkeypatch):
    mounted = _mount_client()
    monkeypatch.setattr(jobs_routes.job_service, "list_recent_jobs", lambda limit=50: JobListResponse(jobs=[]))
    res = mounted.get("/api/v1/jobs")
    assert res.status_code == 200
    assert res.json() == {"jobs": []}


def test_create_job_github_none_guard(monkeypatch):
    mounted = _mount_client()
    monkeypatch.setattr(jobs_routes, "validate_job_source", lambda **kwargs: "github_url")
    res = mounted.post("/api/v1/jobs", data={"auto_repair": "true"})
    assert res.status_code == 400
    assert res.json()["detail"] == "github_url is required."


def test_create_job_upload_none_guard(monkeypatch):
    mounted = _mount_client()
    monkeypatch.setattr(jobs_routes, "validate_job_source", lambda **kwargs: "upload")
    res = mounted.post("/api/v1/jobs", data={"auto_repair": "true"})
    assert res.status_code == 400
    assert res.json()["detail"] == "file is required."


def test_get_status_route(monkeypatch):
    mounted = _mount_client()
    monkeypatch.setattr(
        jobs_routes.job_service,
        "get_job_status",
        lambda job_id: JobStatusResponse(
            job_id=job_id,
            status=JobStatus.DONE,
            progress=100,
            current_step="completed",
            error=None,
        ),
    )
    res = mounted.get("/api/v1/jobs/job_1")
    assert res.status_code == 200
    assert res.json()["status"] == "DONE"


def test_get_artifacts_route(monkeypatch):
    mounted = _mount_client()
    monkeypatch.setattr(
        jobs_routes.job_service,
        "get_job_artifacts",
        lambda job_id: JobArtifactsResponse(job_id=job_id, artifacts=[]),
    )
    res = mounted.get("/api/v1/jobs/job_2/artifacts")
    assert res.status_code == 200
    assert res.json()["job_id"] == "job_2"


def test_delete_route(monkeypatch):
    mounted = _mount_client()
    called = {}
    monkeypatch.setattr(jobs_routes.job_service, "delete_job", lambda job_id: called.setdefault("id", job_id))
    res = mounted.delete("/api/v1/jobs/job_3")
    assert res.status_code == 204
    assert called["id"] == "job_3"


def test_source_archive_route(monkeypatch):
    mounted = _mount_client()
    monkeypatch.setattr(jobs_routes.job_service, "get_source_archive", lambda job_id, phase: (b"zip", f"{job_id}_{phase}.zip"))
    res = mounted.get("/api/v1/jobs/job_4/source/archive?phase=after")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("application/zip")
    assert "job_4_after.zip" in res.headers["content-disposition"]


def test_source_file_route(monkeypatch):
    mounted = _mount_client()
    monkeypatch.setattr(
        jobs_routes.job_service,
        "get_source_file",
        lambda job_id, file_path, phase: SourceFileResponse(file=file_path, lines=["print('x')"], total=1),
    )
    res = mounted.get("/api/v1/jobs/job_5/source?file=/tmp/app.py&phase=before")
    assert res.status_code == 200
    payload = res.json()
    assert payload["file"] == "/tmp/app.py"
    assert payload["total"] == 1


def test_repair_route(monkeypatch):
    mounted = _mount_client()
    monkeypatch.setattr(
        jobs_routes.job_service,
        "trigger_repair",
        lambda job_id, repair_strategy: JobStatusResponse(
            job_id=job_id,
            status=JobStatus.REPAIRING,
            progress=70,
            current_step=f"repair_{repair_strategy}",
            error=None,
        ),
    )
    res = mounted.post("/api/v1/jobs/job_6/repair", json={"repair_strategy": "balanced"})
    assert res.status_code == 202
    assert res.json()["status"] == "REPAIRING"


def test_create_job_upload_passes_storage_key(monkeypatch):
    mounted = _mount_client()
    monkeypatch.setattr(jobs_routes, "validate_job_source", lambda **kwargs: "upload")
    monkeypatch.setattr(jobs_routes.repository_service, "store_uploaded_archive", lambda file: ("repo_1", "uploads/repo_1/repo.zip"))

    captured = {}

    def fake_create_job(**kwargs):
        captured.update(kwargs)
        return JobCreateResponse(
            job_id="job_7",
            status=JobStatus.QUEUED,
            created_at=datetime.now(timezone.utc),
        )

    monkeypatch.setattr(jobs_routes.job_service, "create_job", fake_create_job)
    res = mounted.post(
        "/api/v1/jobs",
        data={"auto_repair": "false"},
        files={"file": ("repo.zip", b"abc", "application/zip")},
    )
    assert res.status_code == 202
    assert captured["storage_key"] == "uploads/repo_1/repo.zip"
