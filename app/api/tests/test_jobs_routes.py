from fastapi.testclient import TestClient
from pathlib import Path

import app.api.routes.jobs as jobs_routes
from app.main import app
from app.schemas.job import Finding


client = TestClient(app)


def setup_function() -> None:
    jobs_routes.job_service.reset_state_for_tests()


def _mock_analyzer_findings(*, phase: str) -> list[Finding]:
    if phase == "after":
        return [
            Finding(
                tool="radon",
                rule_id="CC",
                severity="low",
                category="complexity",
                file="app/service.py",
                line=30,
                message="Cyclomatic complexity reduced.",
                suggestion="Continue decomposition if needed.",
            )
        ]

    return [
        Finding(
            tool="bandit",
            rule_id="B105",
            severity="high",
            category="security",
            file="app/auth.py",
            line=14,
            message="Possible hardcoded password string.",
            suggestion="Use environment-based secret management.",
        ),
        Finding(
            tool="ruff",
            rule_id="F401",
            severity="low",
            category="code_smell",
            file="app/main.py",
            line=2,
            message="Imported but unused name.",
            suggestion="Remove unused imports.",
        ),
        Finding(
            tool="radon",
            rule_id="CC",
            severity="medium",
            category="complexity",
            file="app/service.py",
            line=30,
            message="Cyclomatic complexity is high.",
            suggestion="Split logic into smaller functions.",
        ),
    ]


def _mock_analyzer_findings_with_reports(*, phase: str) -> tuple[list[Finding], dict[str, object]]:
    findings = _mock_analyzer_findings(phase=phase)
    reports = {
        finding.tool: {
            "tool": finding.tool,
            "phase": phase,
            "issues": [
                {
                    "rule_id": finding.rule_id,
                    "message": finding.message,
                    "file": finding.file,
                    "line": finding.line,
                }
            ],
        }
        for finding in findings
    }
    return findings, reports


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


def test_create_job_from_github_url_auto_repair(monkeypatch) -> None:
    monkeypatch.setattr(
        jobs_routes.repository_service,
        "clone_public_repository",
        lambda _: ("repository-1", "abcdef0123456789"),
    )
    monkeypatch.setattr(
        jobs_routes.job_service.analyzer_runner,
        "analyze_repository_with_reports",
        lambda repository_id, source_type, phase: _mock_analyzer_findings_with_reports(phase=phase),
    )
    monkeypatch.setattr(jobs_routes.job_service, "dispatch_repair_pipeline", lambda job_id: None)

    response = client.post(
        "/api/v1/jobs",
        data={"github_url": "https://github.com/acme/repo", "auto_repair": "true"},
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["job_id"].startswith("job_")
    assert payload["status"] == "READY_FOR_REPAIR"


def test_create_job_from_upload_then_repair(monkeypatch) -> None:
    monkeypatch.setattr(
        jobs_routes.job_service.analyzer_runner,
        "analyze_repository_with_reports",
        lambda repository_id, source_type, phase: _mock_analyzer_findings_with_reports(phase=phase),
    )
    monkeypatch.setattr(jobs_routes.job_service, "dispatch_repair_pipeline", lambda job_id: None)

    create_response = client.post(
        "/api/v1/jobs",
        data={"auto_repair": "false", "s3_key": "uploads/repository-2/repo.zip"},
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
    assert repair_response.json()["status"] == "REPAIRING"

    results_response = client.get(f"/api/v1/jobs/{job_id}/results")
    assert results_response.status_code == 200
    results_payload = results_response.json()
    assert results_payload["status"] == "REPAIRING"
    assert results_payload["summary"]["before_total"] == 3
    assert results_payload["summary"]["after_total"] == 0
    assert len(results_payload["patches"]) == 0

    artifacts_response = client.get(f"/api/v1/jobs/{job_id}/artifacts")
    assert artifacts_response.status_code == 200
    artifacts_payload = artifacts_response.json()
    assert artifacts_payload["job_id"] == job_id
    assert len(artifacts_payload["artifacts"]) >= 3
    artifact_types = {artifact["artifact_type"] for artifact in artifacts_payload["artifacts"]}
    assert "analysis_report" in artifact_types
    assert "analysis_report_after" not in artifact_types

    analysis_artifact_keys = [
        artifact["storage_key"]
        for artifact in artifacts_payload["artifacts"]
        if artifact["artifact_type"] == "analysis_report"
    ]
    assert analysis_artifact_keys
    assert all(Path(key).exists() for key in analysis_artifact_keys)

    downloadable_artifact_id = next(
        artifact["artifact_id"]
        for artifact in artifacts_payload["artifacts"]
        if artifact["artifact_type"] == "analysis_report"
    )
    download_response = client.get(f"/api/v1/jobs/{job_id}/artifacts/{downloadable_artifact_id}/download")
    assert download_response.status_code == 200
    assert download_response.headers["content-type"].startswith("application/json")
    assert "tool" in download_response.text


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
