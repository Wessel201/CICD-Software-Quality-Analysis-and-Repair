from fastapi.testclient import TestClient

import app.api.routes.jobs as jobs_routes
from app.main import app


client = TestClient(app)


def setup_function() -> None:
    jobs_routes.job_service._jobs.clear()


def test_create_job_rejects_missing_source() -> None:
    response = client.post("/api/v1/jobs", data={"auto_repair": "true"})

    assert response.status_code == 400
    payload = response.json()
    assert payload["detail"]["error"]["code"] == "INVALID_SOURCE"


def test_create_job_rejects_both_sources(monkeypatch) -> None:
    monkeypatch.setattr(jobs_routes.repository_service, "is_supported_archive", lambda _: True)

    response = client.post(
        "/api/v1/jobs",
        data={"github_url": "https://github.com/acme/repo", "auto_repair": "true"},
        files={"file": ("repo.zip", b"abc", "application/zip")},
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["detail"]["error"]["code"] == "INVALID_SOURCE"


def test_create_job_from_github_url_auto_repair(monkeypatch) -> None:
    monkeypatch.setattr(
        jobs_routes.repository_service,
        "clone_public_repository",
        lambda _: ("repository-1", "abcdef0123456789"),
    )

    response = client.post(
        "/api/v1/jobs",
        data={"github_url": "https://github.com/acme/repo", "auto_repair": "true"},
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["job_id"].startswith("job_")
    assert payload["status"] == "DONE"


def test_create_job_from_upload_then_repair(monkeypatch) -> None:
    monkeypatch.setattr(jobs_routes.repository_service, "is_supported_archive", lambda _: True)
    monkeypatch.setattr(
        jobs_routes.repository_service,
        "store_uploaded_archive",
        lambda _: ("repository-2", "repo.zip"),
    )

    create_response = client.post(
        "/api/v1/jobs",
        data={"auto_repair": "false"},
        files={"file": ("repo.zip", b"abc", "application/zip")},
    )

    assert create_response.status_code == 202
    create_payload = create_response.json()
    assert create_payload["status"] == "READY_FOR_REPAIR"

    job_id = create_payload["job_id"]

    status_response = client.get(f"/api/v1/jobs/{job_id}")
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "READY_FOR_REPAIR"

    repair_response = client.post(
        f"/api/v1/jobs/{job_id}/repair",
        json={"repair_strategy": "balanced"},
    )
    assert repair_response.status_code == 202
    assert repair_response.json()["status"] == "DONE"

    results_response = client.get(f"/api/v1/jobs/{job_id}/results")
    assert results_response.status_code == 200
    results_payload = results_response.json()
    assert results_payload["summary"]["before_total"] == 3
    assert results_payload["summary"]["after_total"] == 1
    assert len(results_payload["patches"]) == 1
