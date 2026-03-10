from urllib.parse import urlparse
from typing import Callable

from fastapi import HTTPException

from app.services.repository_service import RepositoryService


def validate_upload_filename(
    filename: str | None,
    archive_checker: RepositoryService | Callable[[str], bool],
) -> None:
    if not filename:
        raise HTTPException(status_code=400, detail="A repository archive file is required.")

    supports_archive = (
        archive_checker.is_supported_archive(filename)
        if hasattr(archive_checker, "is_supported_archive")
        else archive_checker(filename)
    )

    if not supports_archive:
        raise HTTPException(
            status_code=400,
            detail="Unsupported archive format. Allowed: .zip, .tar, .gz, .tgz, .tar.gz",
        )


def validate_repository_link_url(repo_url: str) -> None:
    parsed_url = urlparse(repo_url)
    if parsed_url.username or parsed_url.password:
        raise HTTPException(status_code=400, detail="Repository URL must not include credentials.")
