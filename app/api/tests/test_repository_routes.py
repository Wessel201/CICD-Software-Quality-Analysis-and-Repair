from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_upload_route_is_not_exposed() -> None:
    response = client.post(
        "/api/repositories/upload",
        files={"file": ("repo.zip", b"dummy-content", "application/zip")},
    )

    assert response.status_code == 404


def test_link_route_is_not_exposed() -> None:
    response = client.post(
        "/api/repositories/link",
        json={"repo_url": "https://user:token@github.com/acme/repo"},
    )

    assert response.status_code == 404


def test_repositories_route_group_is_not_exposed() -> None:
    response = client.post(
        "/api/repositories/link",
        json={"repo_url": "https://github.com/acme/repo"},
    )

    assert response.status_code == 404
