from io import BytesIO
import subprocess
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import app.services.repository_service as repository_service_module
from app.services.repository_service import RepositoryService


class FakeUploadFile:
    def __init__(self, filename: str, content: bytes) -> None:
        self.filename = filename
        self.file = BytesIO(content)


def test_store_uploaded_archive_saves_file(tmp_path) -> None:
    service = RepositoryService(uploads_dir=tmp_path)
    upload = FakeUploadFile("repo.zip", b"abc123")

    submission_id, stored_filename = service.store_uploaded_archive(upload)

    assert stored_filename == "repo.zip"
    stored_path = tmp_path / submission_id / stored_filename
    assert stored_path.exists()
    assert stored_path.read_bytes() == b"abc123"


def test_store_uploaded_archive_rejects_size_limit_and_cleans_directory(tmp_path) -> None:
    service = RepositoryService(uploads_dir=tmp_path)
    service.MAX_REPOSITORY_SIZE_BYTES = 4
    service.CHUNK_SIZE_BYTES = 2
    upload = FakeUploadFile("repo.zip", b"12345")

    with pytest.raises(HTTPException) as exc_info:
        service.store_uploaded_archive(upload)

    assert exc_info.value.status_code == 400
    assert "exceeds maximum allowed size" in str(exc_info.value.detail)
    assert list(tmp_path.iterdir()) == []


def test_clone_public_repository_calls_validation_and_clone(tmp_path, monkeypatch) -> None:
    service = RepositoryService(uploads_dir=tmp_path)
    captured: dict[str, str] = {}

    monkeypatch.setattr(repository_service_module, "uuid4", lambda: "fixed-submission-id")

    def fake_validate(repo_url: str) -> None:
        captured["validated_url"] = repo_url

    def fake_clone(repo_url: str, target_directory) -> str:
        captured["cloned_url"] = repo_url
        captured["target_directory"] = str(target_directory)
        return "0123456789abcdef"

    monkeypatch.setattr(service, "_validate_github_repo_size_limit", fake_validate)
    monkeypatch.setattr(service, "_clone_repository_to_disk", fake_clone)

    submission_id, commit_hash = service.clone_public_repository("https://github.com/acme/repo")

    assert submission_id == "fixed-submission-id"
    assert commit_hash == "0123456789abcdef"
    assert captured["validated_url"] == "https://github.com/acme/repo"
    assert captured["cloned_url"] == "https://github.com/acme/repo"
    assert captured["target_directory"].replace("\\", "/").endswith("fixed-submission-id/source")


def test_clone_public_repository_cleans_up_directory_on_failure(tmp_path, monkeypatch) -> None:
    service = RepositoryService(uploads_dir=tmp_path)

    monkeypatch.setattr(repository_service_module, "uuid4", lambda: "fixed-submission-id")
    monkeypatch.setattr(service, "_validate_github_repo_size_limit", lambda _: None)

    def failing_clone(_, __):
        raise HTTPException(status_code=400, detail="clone failed")

    monkeypatch.setattr(service, "_clone_repository_to_disk", failing_clone)

    with pytest.raises(HTTPException) as exc_info:
        service.clone_public_repository("https://github.com/acme/repo")

    assert exc_info.value.status_code == 400
    assert not (tmp_path / "fixed-submission-id").exists()


def test_resolve_cloned_repository_revision_uses_fallback(monkeypatch, tmp_path) -> None:
    service = RepositoryService(uploads_dir=tmp_path)

    calls = {"count": 0}

    def fake_run(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise subprocess.CalledProcessError(returncode=1, cmd=args[0], stderr="ambiguous HEAD")
        return SimpleNamespace(stdout="abcdef123456\n")

    monkeypatch.setattr(repository_service_module.subprocess, "run", fake_run)

    commit_hash = service._resolve_cloned_repository_revision(tmp_path / "source")

    assert commit_hash == "abcdef123456"
    assert calls["count"] == 2


def test_resolve_cloned_repository_revision_returns_detailed_error(monkeypatch, tmp_path) -> None:
    service = RepositoryService(uploads_dir=tmp_path)

    def always_fail(*args, **kwargs):
        raise subprocess.CalledProcessError(returncode=1, cmd=args[0], stderr="fatal: bad revision 'HEAD'")

    monkeypatch.setattr(repository_service_module.subprocess, "run", always_fail)

    with pytest.raises(HTTPException) as exc_info:
        service._resolve_cloned_repository_revision(tmp_path / "source")

    assert exc_info.value.status_code == 500
    assert "fatal: bad revision 'HEAD'" in str(exc_info.value.detail)
