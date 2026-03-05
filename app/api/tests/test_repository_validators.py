import pytest
from fastapi import HTTPException

from app.services.repository_service import RepositoryService
from app.validators.repository_validators import validate_repository_link_url, validate_upload_filename


def test_validate_upload_filename_requires_filename() -> None:
    service = RepositoryService()

    with pytest.raises(HTTPException) as exc_info:
        validate_upload_filename(None, service)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "A repository archive file is required."


def test_validate_upload_filename_rejects_unsupported_archive() -> None:
    service = RepositoryService()

    with pytest.raises(HTTPException) as exc_info:
        validate_upload_filename("repository.rar", service)

    assert exc_info.value.status_code == 400
    assert "Unsupported archive format" in str(exc_info.value.detail)


def test_validate_upload_filename_accepts_supported_archive() -> None:
    service = RepositoryService()

    validate_upload_filename("repository.zip", service)


def test_validate_repository_link_url_rejects_credentials() -> None:
    with pytest.raises(HTTPException) as exc_info:
        validate_repository_link_url("https://user:token@github.com/acme/repo.git")

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Repository URL must not include credentials."


def test_validate_repository_link_url_accepts_clean_url() -> None:
    validate_repository_link_url("https://github.com/acme/repo")
