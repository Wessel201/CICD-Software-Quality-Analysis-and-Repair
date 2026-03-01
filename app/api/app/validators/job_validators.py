from fastapi import HTTPException, UploadFile
from typing import Callable

from app.schemas.job import ErrorBody, ErrorResponse
from app.validators.repository_validators import validate_repository_link_url, validate_upload_filename


def validate_job_source(
    github_url: str | None,
    file: UploadFile | None,
    *,
    is_supported_archive: Callable[[str], bool],
) -> str:
    has_url = bool(github_url)
    has_file = file is not None

    if has_url == has_file:
        _raise_contract_error(
            code="INVALID_SOURCE",
            message="Provide exactly one source: github_url or file.",
            details={"allowed_sources": "github_url|file"},
            status_code=400,
        )

    if has_url:
        validate_repository_link_url(github_url or "")
        return "github_url"

    validate_upload_filename(file.filename if file else None, is_supported_archive)
    return "upload"


def _raise_contract_error(code: str, message: str, details: dict[str, str], status_code: int) -> None:
    raise HTTPException(
        status_code=status_code,
        detail=ErrorResponse(error=ErrorBody(code=code, message=message, details=details)).model_dump(),
    )
