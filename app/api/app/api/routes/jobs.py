from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.schemas.job import JobCreateResponse, JobRepairRequest, JobResultsResponse, JobStatusResponse
from app.services.job_service import JobService
from app.services.repository_service import RepositoryService
from app.validators.job_validators import validate_job_source


router = APIRouter()
repository_service = RepositoryService()
job_service = JobService()


@router.post("", response_model=JobCreateResponse, status_code=status.HTTP_202_ACCEPTED)
def create_job(
    github_url: str | None = Form(default=None),
    auto_repair: bool = Form(default=True),
    file: UploadFile | None = File(default=None),
) -> JobCreateResponse:
    source_type = validate_job_source(
        github_url=github_url,
        file=file,
        is_supported_archive=repository_service.is_supported_archive,
    )

    if source_type == "github_url":
        if github_url is None:
            raise HTTPException(status_code=400, detail="github_url is required.")
        repository_id, _ = repository_service.clone_public_repository(github_url)
    else:
        if file is None:
            raise HTTPException(status_code=400, detail="file is required.")
        repository_id, _ = repository_service.store_uploaded_archive(file)

    return job_service.create_job(
        source_type=source_type,
        source_reference=repository_id,
        auto_repair=auto_repair,
    )


@router.get("/{job_id}", response_model=JobStatusResponse)
def get_job_status(job_id: str) -> JobStatusResponse:
    return job_service.get_job_status(job_id)


@router.get("/{job_id}/results", response_model=JobResultsResponse)
def get_job_results(job_id: str) -> JobResultsResponse:
    return job_service.get_job_results(job_id)


@router.post("/{job_id}/repair", response_model=JobStatusResponse, status_code=status.HTTP_202_ACCEPTED)
def repair_job(job_id: str, payload: JobRepairRequest) -> JobStatusResponse:
    return job_service.trigger_repair(job_id=job_id, repair_strategy=payload.repair_strategy)
