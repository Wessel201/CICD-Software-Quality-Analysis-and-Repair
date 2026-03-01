from fastapi import HTTPException
from fastapi.testclient import TestClient

import app.api.routes.repositories as repositories_routes
from app.main import app


client = TestClient(app)


def test_upload_route_validates_and_delegates(monkeypatch) -> None:
    calls: dict[str, object] = {}

    def fake_validate_upload_filename(filename, service) -> None:
        calls["filename"] = filename
        calls["service"] = service

    def fake_store_uploaded_archive(upload_file):
        calls["stored_filename"] = upload_file.filename
        return "submission-1", "repo.zip"

    monkeypatch.setattr(repositories_routes, "validate_upload_filename", fake_validate_upload_filename)
    monkeypatch.setattr(repositories_routes.repository_service, "store_uploaded_archive", fake_store_uploaded_archive)

    response = client.post(
        "/api/repositories/upload",
        files={"file": ("repo.zip", b"dummy-content", "application/zip")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["submission_id"] == "submission-1"
    assert payload["source_type"] == "upload"
    assert calls["filename"] == "repo.zip"
    assert calls["service"] is repositories_routes.repository_service
    assert calls["stored_filename"] == "repo.zip"


def test_link_route_validation_error_is_returned(monkeypatch) -> None:
    def fake_validate_repository_link_url(_: str) -> None:
        raise HTTPException(status_code=400, detail="Repository URL must not include credentials.")

    monkeypatch.setattr(repositories_routes, "validate_repository_link_url", fake_validate_repository_link_url)

    response = client.post(
        "/api/repositories/link",
        json={"repo_url": "https://user:token@github.com/acme/repo"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Repository URL must not include credentials."


def test_link_route_delegates_to_service_after_validation(monkeypatch) -> None:
    calls: dict[str, object] = {}

    def fake_validate_repository_link_url(repo_url: str) -> None:
        calls["validated_url"] = repo_url

    def fake_clone_public_repository(repo_url: str):
        calls["cloned_url"] = repo_url
        return "submission-2", "fedcba9876543210"

    monkeypatch.setattr(repositories_routes, "validate_repository_link_url", fake_validate_repository_link_url)
    monkeypatch.setattr(repositories_routes.repository_service, "clone_public_repository", fake_clone_public_repository)

    response = client.post(
        "/api/repositories/link",
        json={"repo_url": "https://github.com/acme/repo"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["submission_id"] == "submission-2"
    assert payload["source_type"] == "git_link"
    assert payload["detail"] == "Public repository cloned successfully at commit fedcba987654."
    assert calls["validated_url"] == "https://github.com/acme/repo"
    assert calls["cloned_url"] == "https://github.com/acme/repo"
