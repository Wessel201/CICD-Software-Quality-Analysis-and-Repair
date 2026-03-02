from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import (
    AnalysisPhase,
    AnalysisRunModel,
    ArtifactModel,
    FindingModel,
    JobModel,
    JobStatusDb,
    RepositoryModel,
    SourceType,
)
from app.schemas.job import ArtifactInfo, Finding, PatchInfo


@dataclass
class JobSnapshot:
    job_id: str
    status: JobStatusDb
    progress: int
    current_step: str
    error_message: str | None
    created_at: datetime


@dataclass
class JobContext:
    job_id: str
    repository_id: str
    source_type: str


class JobRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert_repository(self, repository_id: str, source_type: str) -> RepositoryModel:
        repository = self.session.get(RepositoryModel, repository_id)
        if repository is None:
            repository = RepositoryModel(
                id=repository_id,
                source_type=SourceType(source_type),
                github_url=repository_id if source_type == SourceType.GITHUB_URL.value else None,
                storage_key=repository_id if source_type == SourceType.UPLOAD.value else None,
            )
            self.session.add(repository)
            self.session.flush()
        return repository

    def create_job(self, job_id: str, repository_id: str, auto_repair: bool) -> JobModel:
        job = JobModel(
            id=job_id,
            repository_id=repository_id,
            status=JobStatusDb.QUEUED,
            progress=0,
            auto_repair=auto_repair,
            current_step="queued",
        )
        self.session.add(job)
        self.session.flush()
        return job

    def get_job(self, job_id: str) -> JobModel:
        job = self.session.get(JobModel, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found.")
        return job

    def update_job_state(
        self,
        job_id: str,
        *,
        status: JobStatusDb,
        progress: int,
        current_step: str,
        error_message: str | None = None,
        error_code: str | None = None,
    ) -> JobModel:
        job = self.get_job(job_id)
        job.status = status
        job.progress = progress
        job.current_step = current_step
        job.error_message = error_message
        job.error_code = error_code
        if status in {JobStatusDb.FETCHING, JobStatusDb.ANALYZING, JobStatusDb.REPAIRING, JobStatusDb.REANALYZING}:
            if job.started_at is None:
                job.started_at = datetime.now()
        if status in {JobStatusDb.DONE, JobStatusDb.FAILED}:
            job.finished_at = datetime.now()
        self.session.flush()
        return job

    def replace_findings_for_phase(self, job_id: str, phase: AnalysisPhase, findings: list[Finding]) -> None:
        existing_run = self.session.execute(
            select(AnalysisRunModel).where(AnalysisRunModel.job_id == job_id, AnalysisRunModel.phase == phase)
        ).scalar_one_or_none()

        if existing_run is not None:
            self.session.execute(delete(FindingModel).where(FindingModel.analysis_run_id == existing_run.id))
            self.session.delete(existing_run)
            self.session.flush()

        run = AnalysisRunModel(
            id=str(uuid4()),
            job_id=job_id,
            phase=phase,
            summary_json={"count": len(findings)},
            started_at=datetime.now(),
            finished_at=datetime.now(),
        )
        self.session.add(run)
        self.session.flush()

        for finding in findings:
            finding_row = FindingModel(
                analysis_run_id=run.id,
                tool=finding.tool,
                rule_id=finding.rule_id,
                severity=finding.severity,
                category=finding.category,
                file_path=finding.file,
                line=finding.line,
                message=finding.message,
                suggestion=finding.suggestion,
                fingerprint=f"{finding.tool}:{finding.rule_id}:{finding.file}:{finding.line}",
            )
            self.session.add(finding_row)

        self.session.flush()

    def replace_patches(self, job_id: str, patches: list[PatchInfo]) -> None:
        self.session.execute(delete(ArtifactModel).where(ArtifactModel.job_id == job_id, ArtifactModel.type == "patch"))
        for patch in patches:
            self.session.add(
                ArtifactModel(
                    job_id=job_id,
                    type="patch",
                    storage_key=patch.diff_url,
                    content_type="text/x-diff",
                )
            )
        self.session.flush()

    def replace_artifacts_by_type(self, job_id: str, artifact_type: str, artifacts: list[ArtifactInfo]) -> None:
        self.session.execute(delete(ArtifactModel).where(ArtifactModel.job_id == job_id, ArtifactModel.type == artifact_type))
        for artifact in artifacts:
            self.session.add(
                ArtifactModel(
                    job_id=job_id,
                    type=artifact.artifact_type,
                    storage_key=artifact.storage_key,
                    content_type=artifact.content_type,
                )
            )
        self.session.flush()

    def get_job_snapshot(self, job_id: str) -> JobSnapshot:
        job = self.get_job(job_id)
        return JobSnapshot(
            job_id=job.id,
            status=job.status,
            progress=job.progress,
            current_step=job.current_step,
            error_message=job.error_message,
            created_at=job.created_at,
        )

    def get_job_context(self, job_id: str) -> JobContext:
        job = self.get_job(job_id)
        repository = self.session.get(RepositoryModel, job.repository_id)
        if repository is None:
            raise HTTPException(status_code=404, detail="Repository not found for job.")

        return JobContext(
            job_id=job.id,
            repository_id=repository.id,
            source_type=repository.source_type.value,
        )

    def get_findings_for_phase(self, job_id: str, phase: AnalysisPhase) -> list[Finding]:
        run = self.session.execute(
            select(AnalysisRunModel).where(AnalysisRunModel.job_id == job_id, AnalysisRunModel.phase == phase)
        ).scalar_one_or_none()
        if run is None:
            return []

        finding_rows = self.session.execute(
            select(FindingModel).where(FindingModel.analysis_run_id == run.id).order_by(FindingModel.id.asc())
        ).scalars()

        return [
            Finding(
                tool=row.tool,
                rule_id=row.rule_id or "",
                severity=row.severity,
                category=row.category or "",
                file=row.file_path,
                line=row.line or 0,
                message=row.message,
                suggestion=row.suggestion or "",
            )
            for row in finding_rows
        ]

    def get_patches(self, job_id: str) -> list[PatchInfo]:
        rows = self.session.execute(
            select(ArtifactModel).where(ArtifactModel.job_id == job_id, ArtifactModel.type == "patch").order_by(ArtifactModel.id.asc())
        ).scalars()
        patches: list[PatchInfo] = []
        for row in rows:
            file_hint = row.storage_key.split("/")[-1].replace(".patch", ".py")
            patches.append(PatchInfo(file=file_hint or "unknown", diff_url=row.storage_key))
        return patches

    def get_artifacts(self, job_id: str) -> list[ArtifactInfo]:
        rows = self.session.execute(
            select(ArtifactModel).where(ArtifactModel.job_id == job_id).order_by(ArtifactModel.id.asc())
        ).scalars()
        return [
            ArtifactInfo(
                artifact_id=row.id,
                artifact_type=row.type,
                storage_key=row.storage_key,
                content_type=row.content_type,
            )
            for row in rows
        ]

    def get_artifact_for_job(self, job_id: str, artifact_id: int) -> ArtifactModel:
        artifact = self.session.execute(
            select(ArtifactModel).where(ArtifactModel.job_id == job_id, ArtifactModel.id == artifact_id)
        ).scalar_one_or_none()
        if artifact is None:
            raise HTTPException(status_code=404, detail="Artifact not found for job.")
        return artifact

    def clear_all(self) -> None:
        self.session.execute(delete(FindingModel))
        self.session.execute(delete(AnalysisRunModel))
        self.session.execute(delete(ArtifactModel))
        self.session.execute(delete(JobModel))
        self.session.execute(delete(RepositoryModel))
        self.session.flush()
