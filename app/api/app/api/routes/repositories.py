from fastapi import APIRouter, File, UploadFile

from app.schemas.repository import GitRepositoryLinkRequest, RepositorySubmissionResponse
from app.services.repository_service import RepositoryService
from app.validators.repository_validators import validate_repository_link_url, validate_upload_filename


router = APIRouter()
repository_service = RepositoryService()

@router.post("/upload", response_model=RepositorySubmissionResponse)
def upload_repository(file: UploadFile = File(...)) -> RepositorySubmissionResponse:
    validate_upload_filename(file.filename, repository_service)

    submission_id, stored_filename = repository_service.store_uploaded_archive(file)

    return RepositorySubmissionResponse(
        submission_id=submission_id,
        source_type="upload",
        detail=f"Repository archive stored as {stored_filename}",
    )


@router.post("/link", response_model=RepositorySubmissionResponse)
def submit_repository_link(payload: GitRepositoryLinkRequest) -> RepositorySubmissionResponse:
    validate_repository_link_url(str(payload.repo_url))

    submission_id, commit_hash = repository_service.clone_public_repository(str(payload.repo_url))

    return RepositorySubmissionResponse(
        submission_id=submission_id,
        source_type="git_link",
        detail=f"Public repository cloned successfully at commit {commit_hash[:12]}.",
    )
