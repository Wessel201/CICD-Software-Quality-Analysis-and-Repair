from fastapi.testclient import TestClient

import app.api.routes.jobs as jobs_routes
from app.main import app


client = TestClient(app)


def setup_function() -> None:
    jobs_routes.job_service.reset_state_for_tests()


def test_create_job_rejects_missing_source() -> None:
    response = client.post("/api/v1/jobs", data={"auto_repair": "true"})

    assert response.status_code == 400
    payload = response.json()
    assert payload["error"]["code"] == "INVALID_SOURCE"


def test_create_job_rejects_both_sources(monkeypatch) -> None:
    response = client.post(
        "/api/v1/jobs",
        data={
            "github_url": "https://github.com/acme/repo",
            "s3_key": "uploads/submission/repo.zip",
            "auto_repair": "true",
        },
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["error"]["code"] == "INVALID_SOURCE"


def test_create_job_from_github_url_queues_analysis(monkeypatch) -> None:
    submissions: list[dict[str, object]] = []
    monkeypatch.setattr(
        jobs_routes.job_service.cloud_manager,
        "submit_job",
        lambda payload: submissions.append(payload),
    )

    response = client.post(
        "/api/v1/jobs",
        data={"github_url": "https://github.com/acme/repo", "auto_repair": "true"},
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["job_id"].startswith("job_")
    assert payload["status"] == "QUEUED"
    assert submissions == [
        {
            "job_id": payload["job_id"],
            "action": "analyze",
            "auto_repair": True,
        }
    ]


def test_create_job_from_upload_queues_analysis(monkeypatch) -> None:
    submissions: list[dict[str, object]] = []
    monkeypatch.setattr(
        jobs_routes.job_service.cloud_manager,
        "submit_job",
        lambda payload: submissions.append(payload),
    )

    create_response = client.post(
        "/api/v1/jobs",
        data={"auto_repair": "false", "s3_key": "uploads/repository-2/repo.zip"},
    )

    assert create_response.status_code == 202
    create_payload = create_response.json()
    assert create_payload["status"] == "QUEUED"
    assert submissions == [
        {
            "job_id": create_payload["job_id"],
            "action": "analyze",
            "auto_repair": False,
        }
    ]

    job_id = create_payload["job_id"]

    status_response = client.get(f"/api/v1/jobs/{job_id}")
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "QUEUED"


def test_download_artifact_redirects_for_presigned_urls(monkeypatch) -> None:
    monkeypatch.setattr(
        jobs_routes.job_service,
        "get_job_artifact_download",
        lambda job_id, artifact_id: ("https://signed.example/download", "application/json"),
    )

    response = client.get("/api/v1/jobs/job_123/artifacts/9/download", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "https://signed.example/download"


def test_request_upload_url(monkeypatch) -> None:
    monkeypatch.setattr(
        jobs_routes.cloud_manager,
        "generate_upload_url",
        lambda user_id, filename: ("https://signed.example/put", "uploads/sub/repo.zip"),
    )
    response = client.post("/api/v1/jobs/upload-url", json={"filename": "repo.zip"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["upload_url"] == "https://signed.example/put"
    assert payload["s3_key"] == "uploads/sub/repo.zip"


def test_create_job_rejects_direct_file_upload(monkeypatch) -> None:
    response = client.post(
        "/api/v1/jobs",
        data={"auto_repair": "false"},
        files={"file": ("repo.zip", b"abc", "application/zip")},
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["error"]["code"] == "DIRECT_UPLOAD_REQUIRED"
