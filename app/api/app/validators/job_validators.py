from fastapi import HTTPException, UploadFile
from typing import Callable

from app.schemas.job import ErrorBody, ErrorResponse
from app.validators.repository_validators import validate_repository_link_url, validate_upload_filename


def validate_job_source(
    github_url: str | None,
    s3_key: str | None,
    file: UploadFile | None,
    *,
    is_supported_archive: Callable[[str], bool],
) -> str:
    has_url = bool(github_url)
    has_s3_key = bool(s3_key)
    has_file = file is not None

    if has_file:
        _raise_contract_error(
            code="DIRECT_UPLOAD_REQUIRED",
            message="Direct file upload is disabled. Request an upload URL and upload directly to S3.",
            details={"endpoint": "/api/v1/jobs/upload-url"},
            status_code=400,
        )

    if (1 if has_url else 0) + (1 if has_s3_key else 0) != 1:
        _raise_contract_error(
            code="INVALID_SOURCE",
            message="Provide exactly one source: github_url or s3_key.",
            details={"allowed_sources": "github_url|s3_key"},
            status_code=400,
        )

    if has_url:
        validate_repository_link_url(github_url or "")
        return "github_url"

    if not s3_key or not s3_key.startswith("uploads/"):
        _raise_contract_error(
            code="INVALID_S3_KEY",
            message="s3_key must start with uploads/.",
            details={"example": "uploads/<submission_id>/repo.zip"},
            status_code=400,
        )

    return "upload"


def _raise_contract_error(code: str, message: str, details: dict[str, str], status_code: int) -> None:
    raise HTTPException(
        status_code=status_code,
        detail=ErrorResponse(error=ErrorBody(code=code, message=message, details=details)).model_dump(),
    )
