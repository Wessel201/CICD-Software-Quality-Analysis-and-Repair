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
    monkeypatch.setattr(
        jobs_routes.job_service.analyzer_runner,
        "analyze_repository_with_reports",
        lambda repository_id, source_type, phase: _mock_analyzer_findings_with_reports(phase=phase),
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
    monkeypatch.setattr(
        jobs_routes.job_service.analyzer_runner,
        "analyze_repository_with_reports",
        lambda repository_id, source_type, phase: _mock_analyzer_findings_with_reports(phase=phase),
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

    artifacts_response = client.get(f"/api/v1/jobs/{job_id}/artifacts")
    assert artifacts_response.status_code == 200
    artifacts_payload = artifacts_response.json()
    assert artifacts_payload["job_id"] == job_id
    assert len(artifacts_payload["artifacts"]) == 5
    artifact_types = {artifact["artifact_type"] for artifact in artifacts_payload["artifacts"]}
    assert "patch" in artifact_types
    assert "analysis_report" in artifact_types
    assert "analysis_report_after" in artifact_types

    analysis_artifact_keys = [
        artifact["storage_key"]
        for artifact in artifacts_payload["artifacts"]
        if artifact["artifact_type"] in {"analysis_report", "analysis_report_after"}
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
