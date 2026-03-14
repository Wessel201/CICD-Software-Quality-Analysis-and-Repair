from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, RedirectResponse, Response

from app.schemas.job import JobArtifactsResponse, JobCreateResponse, JobListResponse, JobRepairRequest, JobResultsResponse, JobStatusResponse, SourceFileResponse
from app.services.job_service import JobService
from app.services.repository_service import RepositoryService
from app.validators.job_validators import validate_job_source


router = APIRouter()
repository_service = RepositoryService()
job_service = JobService()


@router.get("", response_model=JobListResponse)
def list_jobs(limit: int = Query(default=50, ge=1, le=100)) -> JobListResponse:
    return job_service.list_recent_jobs(limit=limit)


@router.post("", response_model=JobCreateResponse, status_code=status.HTTP_202_ACCEPTED)
def create_job(
    github_url: str | None = Form(default=None),
    auto_repair: bool = Form(default=True),
    file: UploadFile | None = File(default=None),
) -> JobCreateResponse:
    storage_key: str | None = None
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
        repository_id, storage_key = repository_service.store_uploaded_archive(file)

    return job_service.create_job(
        source_type=source_type,
        source_reference=repository_id,
        auto_repair=auto_repair,
        github_url=github_url if source_type == "github_url" else None,
        storage_key=storage_key if source_type == "upload" else None,
    )


@router.get("/{job_id}", response_model=JobStatusResponse)
def get_job_status(job_id: str) -> JobStatusResponse:
    return job_service.get_job_status(job_id)


@router.get("/{job_id}/results", response_model=JobResultsResponse)
def get_job_results(job_id: str) -> JobResultsResponse:
    return job_service.get_job_results(job_id)


@router.get("/{job_id}/artifacts", response_model=JobArtifactsResponse)
def get_job_artifacts(job_id: str) -> JobArtifactsResponse:
    return job_service.get_job_artifacts(job_id)


@router.get("/{job_id}/artifacts/{artifact_id}/download")
def download_job_artifact(job_id: str, artifact_id: int) -> Response:
    artifact_path, content_type = job_service.get_job_artifact_download(job_id=job_id, artifact_id=artifact_id)
    if isinstance(artifact_path, str) and artifact_path.startswith("http"):
        return RedirectResponse(url=artifact_path, status_code=status.HTTP_307_TEMPORARY_REDIRECT)

    return FileResponse(
        path=artifact_path,
        media_type=content_type or "application/octet-stream",
        filename=artifact_path.name,
    )


@router.post("/{job_id}/repair", response_model=JobStatusResponse, status_code=status.HTTP_202_ACCEPTED)
def repair_job(job_id: str, payload: JobRepairRequest) -> JobStatusResponse:
    return job_service.trigger_repair(job_id=job_id, repair_strategy=payload.repair_strategy)


@router.delete("/{job_id}", status_code=204)
def delete_job(job_id: str) -> None:
    job_service.delete_job(job_id)


@router.get("/{job_id}/source/archive")
def download_source_archive(
    job_id: str,
    phase: str = Query(default="before", pattern="^(before|after)$"),
) -> Response:
    zip_bytes, filename = job_service.get_source_archive(job_id=job_id, phase=phase)
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=\"{filename}\""},
    )


@router.get("/{job_id}/source", response_model=SourceFileResponse)
def get_job_source_file(
    job_id: str,
    file: str = Query(..., description="Absolute path to the source file (as returned in findings)"),
    phase: str = Query(default="before", pattern="^(before|after)$"),
) -> SourceFileResponse:
    return job_service.get_source_file(job_id=job_id, file_path=file, phase=phase)
