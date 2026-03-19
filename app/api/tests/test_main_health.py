from fastapi.testclient import TestClient
from fastapi import HTTPException, Query
import importlib
import pytest

from sqlalchemy.exc import OperationalError, SQLAlchemyError

import app.main as main_module
from app.main import app


client = TestClient(app)


def test_health_check() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_auto_init_db_branch(monkeypatch) -> None:
    called = {"count": 0}
    monkeypatch.setenv("AUTO_INIT_DB", "true")

    import app.db.init_db as init_db_module
    monkeypatch.setattr(init_db_module, "init_db", lambda: called.__setitem__("count", called["count"] + 1))

    import app.main as main_module
    importlib.reload(main_module)

    assert called["count"] == 1


def test_api_key_required_for_api_routes_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("API_KEY", "test-key")

    no_key_response = client.get("/api/v1/jobs")
    assert no_key_response.status_code == 401

    with_key_response = client.get("/api/v1/jobs", headers={"x-api-key": "test-key"})
    assert with_key_response.status_code == 200

    monkeypatch.delenv("API_KEY", raising=False)


@pytest.mark.parametrize(
    ("status_code", "message", "expected"),
    [
        (500, "database connection failed", "DB_UNAVAILABLE"),
        (500, "repository source not found", "SOURCE_DIRECTORY_MISSING"),
        (500, "cloned source directory is missing", "SOURCE_DIRECTORY_MISSING"),
        (500, "no uploaded archive found", "SOURCE_ARCHIVE_MISSING"),
        (500, "source file not found", "SOURCE_FILE_NOT_FOUND"),
        (500, "failed to read source file", "SOURCE_FILE_READ_FAILED"),
        (500, "outside the job source directory", "SOURCE_PATH_FORBIDDEN"),
        (500, "s3_bucket_name is not configured", "S3_BUCKET_NOT_CONFIGURED"),
        (500, "failed to generate artifact download url", "S3_DOWNLOAD_URL_FAILED"),
        (500, "failed to generate upload url", "S3_UPLOAD_URL_FAILED"),
        (500, "failed to upload repository archive to s3", "S3_UPLOAD_FAILED"),
        (500, "artifact file is missing from storage", "ARTIFACT_STORAGE_MISSING"),
        (500, "artifact not found", "ARTIFACT_NOT_FOUND"),
        (500, "repository not found for job", "REPOSITORY_NOT_FOUND"),
        (500, "job not found", "JOB_NOT_FOUND"),
        (500, "failed to submit job to sqs", "SQS_SUBMIT_FAILED"),
        (500, "sqs_queue_url is not configured", "SQS_QUEUE_NOT_CONFIGURED"),
        (401, "anything", "AUTH_INVALID_API_KEY"),
        (403, "anything", "FORBIDDEN"),
        (404, "anything", "NOT_FOUND"),
        (409, "anything", "STATE_CONFLICT"),
        (422, "anything", "REQUEST_INVALID"),
        (500, "anything", "INTERNAL_ERROR"),
    ],
)
def test_infer_error_code_branches(status_code: int, message: str, expected: str) -> None:
    assert main_module._infer_error_code(status_code, message) == expected


def _register_main_test_routes() -> None:
    if any(getattr(route, "path", "") == "/api/v1/_test_validation" for route in app.routes):
        return

    @app.get("/api/v1/_test_validation")
    def _test_validation(limit: int = Query(...)) -> dict[str, int]:
        return {"limit": limit}

    @app.get("/api/v1/_test_db_operational")
    def _test_db_operational() -> None:
        raise OperationalError("select 1", {}, Exception("database connection failed"))

    @app.get("/api/v1/_test_db_sqlalchemy")
    def _test_db_sqlalchemy() -> None:
        raise SQLAlchemyError("query failed")

    @app.get("/api/v1/_test_unhandled")
    def _test_unhandled() -> None:
        raise RuntimeError("boom")

    @app.get("/api/v1/_test_http_exception")
    def _test_http_exception() -> None:
        raise HTTPException(status_code=404, detail="resource missing")


def test_validation_exception_handler_branch() -> None:
    _register_main_test_routes()
    response = client.get("/api/v1/_test_validation?limit=not-an-int")
    assert response.status_code == 422
    payload = response.json()
    assert payload["error"]["code"] == "REQUEST_VALIDATION_FAILED"


def test_db_operational_exception_handler_branch() -> None:
    _register_main_test_routes()
    response = client.get("/api/v1/_test_db_operational")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DB_UNAVAILABLE"


def test_sqlalchemy_exception_handler_branch() -> None:
    _register_main_test_routes()
    response = client.get("/api/v1/_test_db_sqlalchemy")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "DB_QUERY_FAILED"


def test_unhandled_exception_and_middleware_failure_branch() -> None:
    _register_main_test_routes()
    non_raising_client = TestClient(app, raise_server_exceptions=False)
    response = non_raising_client.get("/api/v1/_test_unhandled")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "API_INTERNAL_ERROR"


def test_http_exception_handler_plain_detail_branch() -> None:
    _register_main_test_routes()
    response = client.get("/api/v1/_test_http_exception")
    assert response.status_code == 404
    payload = response.json()
    assert payload["error"]["code"] == "NOT_FOUND"
    assert payload["detail"] == "resource missing"
