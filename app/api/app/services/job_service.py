from threading import Lock
from uuid import uuid4
import os
from pathlib import Path
import logging

from fastapi import HTTPException

from app.db.models import AnalysisPhase, JobStatusDb
from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.cloud import CloudQualityManager
from app.repositories.job_repository import JobRepository
from app.services.analyzer_runner import AnalyzerRunner
from app.schemas.job import Finding, JobCreateResponse, JobListItem, JobListResponse, JobResultsResponse, JobStatus, JobStatusResponse, JobSummary
from app.schemas.job import JobArtifactsResponse, SourceFileResponse


class JobService:
    _lock = Lock()
    _allowed_transitions: dict[JobStatusDb, set[JobStatusDb]] = {
        JobStatusDb.QUEUED: {JobStatusDb.FETCHING, JobStatusDb.FAILED},
        JobStatusDb.FETCHING: {JobStatusDb.ANALYZING, JobStatusDb.FAILED},
        JobStatusDb.ANALYZING: {JobStatusDb.READY_FOR_REPAIR, JobStatusDb.DONE, JobStatusDb.FAILED},
        JobStatusDb.READY_FOR_REPAIR: {JobStatusDb.REPAIRING, JobStatusDb.FAILED},
        JobStatusDb.REPAIRING: {JobStatusDb.REANALYZING, JobStatusDb.FAILED},
        JobStatusDb.REANALYZING: {JobStatusDb.DONE, JobStatusDb.FAILED},
        JobStatusDb.DONE: set(),
        JobStatusDb.FAILED: set(),
    }

    def __init__(self, analyzer_runner: AnalyzerRunner | None = None) -> None:
        self.analyzer_runner = analyzer_runner or AnalyzerRunner()
        self.cloud_manager = CloudQualityManager()
        self.logger = logging.getLogger(__name__)

    def create_job(
        self,
        source_type: str,
        source_reference: str,
        auto_repair: bool,
        github_url: str | None = None,
        storage_key: str | None = None,
    ) -> JobCreateResponse:
        job_id = f"job_{uuid4().hex[:12]}"
        created_at = None
        self.logger.info("Creating job", extra={"event": "job_create_start", "job_id": job_id})

        with self._lock:
            with SessionLocal() as session:
                repository = JobRepository(session)
                repository.upsert_repository(
                    repository_id=source_reference,
                    source_type=source_type,
                    github_url=github_url,
                    storage_key=storage_key,
                )
                job = repository.create_job(job_id=job_id, repository_id=source_reference, auto_repair=auto_repair)
                created_at = job.created_at
                session.commit()

        self.dispatch_analysis_pipeline(job_id=job_id, auto_repair=auto_repair)
        self.logger.info("Dispatched analysis pipeline", extra={"event": "job_analysis_dispatched", "job_id": job_id})

        current_status = self.get_job_status(job_id)

        if created_at is None:
            raise HTTPException(status_code=500, detail="Failed to persist job creation timestamp.")

        self.logger.info("Job creation complete", extra={"event": "job_create_complete", "job_id": job_id, "status": current_status.status})
        return JobCreateResponse(job_id=job_id, status=current_status.status, created_at=created_at)

    def get_job_status(self, job_id: str) -> JobStatusResponse:
        with SessionLocal() as session:
            repository = JobRepository(session)
            snapshot = repository.get_job_snapshot(job_id)
            return JobStatusResponse(
                job_id=snapshot.job_id,
                status=JobStatus(snapshot.status.value),
                progress=snapshot.progress,
                current_step=snapshot.current_step,
                error=snapshot.error_message,
            )

    def delete_job(self, job_id: str) -> None:
        self.logger.info("Deleting job", extra={"event": "job_delete_start", "job_id": job_id})
        with self._lock:
            with SessionLocal() as session:
                repository = JobRepository(session)
                repository.delete_job(job_id)
                session.commit()
        self.logger.info("Job deleted", extra={"event": "job_delete_complete", "job_id": job_id})

    def list_recent_jobs(self, limit: int = 50) -> JobListResponse:
        with SessionLocal() as session:
            repository = JobRepository(session)
            snapshots = repository.list_recent_jobs(limit=limit)

        jobs: list[JobListItem] = []
        for s in snapshots:
            # For local upload jobs, resolve UUID folder to human-friendly archive filename.
            label = s.source_label
            if label and not label.startswith("http") and "/" not in label:
                # Looks like a UUID storage_key; resolve filename from disk
                upload_path = self.analyzer_runner.uploads_dir / label
                if upload_path.is_dir():
                    archive_files = [
                        f.name for f in upload_path.iterdir()
                        if f.is_file() and not f.name.startswith(".")
                    ]
                    if archive_files:
                        label = archive_files[0]
                    else:
                        # May be a GitHub clone (UUID dir has source/ but no archive files).
                        # Try to recover the repo name from the git remote config.
                        git_config = upload_path / "source" / ".git" / "config"
                        if git_config.exists():
                            try:
                                import configparser
                                cfg = configparser.ConfigParser()
                                cfg.read(git_config)
                                git_url = cfg.get('remote "origin"', "url")
                                parts = [p for p in git_url.rstrip("/").split("/") if p]
                                if parts:
                                    label = parts[-1].removesuffix(".git")
                            except Exception:
                                pass  # keep UUID as fallback
            jobs.append(
                JobListItem(
                    job_id=s.job_id,
                    status=JobStatus(s.status.value),
                    created_at=s.created_at,
                    finished_at=s.finished_at,
                    source_label=label,
                )
            )
        return JobListResponse(jobs=jobs)

    def get_job_results(self, job_id: str) -> JobResultsResponse:
        with SessionLocal() as session:
            repository = JobRepository(session)
            snapshot = repository.get_job_snapshot(job_id)
            before = repository.get_findings_for_phase(job_id=job_id, phase=AnalysisPhase.BEFORE)
            after = repository.get_findings_for_phase(job_id=job_id, phase=AnalysisPhase.AFTER)
            patches = repository.get_patches(job_id=job_id)
            job_context = repository.get_job_context(job_id)

            if not before:
                raise HTTPException(status_code=409, detail="Analysis results are not available yet.")

            self._attach_snippets(
                findings=before,
                repository_id=job_context.repository_id,
                source_type=job_context.source_type,
                phase="before",
                storage_key=job_context.storage_key,
                github_url=job_context.github_url,
            )
            self._attach_snippets(
                findings=after,
                repository_id=job_context.repository_id,
                source_type=job_context.source_type,
                phase="after",
                storage_key=job_context.storage_key,
                github_url=job_context.github_url,
            )

            # Don't gate on 'after' — it's empty when repair hasn't run yet (READY_FOR_REPAIR)
            summary = self._build_summary(before, after)
            return JobResultsResponse(
                job_id=job_id,
                status=JobStatus(snapshot.status.value),
                summary=summary,
                before=before,
                after=after,
                patches=patches,
            )

    def get_job_artifacts(self, job_id: str) -> JobArtifactsResponse:
        with SessionLocal() as session:
            repository = JobRepository(session)
            snapshot = repository.get_job_snapshot(job_id)
            artifacts = repository.get_artifacts(job_id=job_id)
            return JobArtifactsResponse(job_id=snapshot.job_id, artifacts=artifacts)

    def get_source_file(self, job_id: str, file_path: str, phase: str = "before") -> SourceFileResponse:
        with SessionLocal() as session:
            repository = JobRepository(session)
            job_context = repository.get_job_context(job_id)
        lines = self.analyzer_runner.read_source_file(
            repository_id=job_context.repository_id,
            source_type=job_context.source_type,
            file_path=file_path,
            phase=phase,
            storage_key=job_context.storage_key,
            github_url=job_context.github_url,
        )
        return SourceFileResponse(file=file_path, lines=lines, total=len(lines))

    def get_source_archive(self, job_id: str, phase: str = "before") -> tuple[bytes, str]:
        with SessionLocal() as session:
            repository = JobRepository(session)
            job_context = repository.get_job_context(job_id)
        zip_bytes = self.analyzer_runner.build_source_archive(
            repository_id=job_context.repository_id,
            source_type=job_context.source_type,
            phase=phase,
            storage_key=job_context.storage_key,
            github_url=job_context.github_url,
        )
        filename = f"{job_id}_{phase}_source.zip"
        return zip_bytes, filename

    def get_job_artifact_download(self, job_id: str, artifact_id: int) -> tuple[str | Path, str | None]:
        with SessionLocal() as session:
            repository = JobRepository(session)
            repository.get_job_snapshot(job_id)
            artifact = repository.get_artifact_for_job(job_id=job_id, artifact_id=artifact_id)

        if artifact.storage_key.startswith("s3://"):
            storage_key = artifact.storage_key.removeprefix("s3://")
            return self.cloud_manager.generate_download_url(storage_key), artifact.content_type

        if artifact.storage_key.startswith("uploads/") and os.getenv("S3_BUCKET_NAME"):
            return self.cloud_manager.generate_download_url(artifact.storage_key), artifact.content_type

        artifact_path = Path(artifact.storage_key)
        if not artifact_path.is_absolute():
            artifact_path = Path.cwd() / artifact_path

        artifact_path = artifact_path.resolve()
        allowed_root = (Path.cwd() / "uploads" / job_id / "artifacts").resolve()

        if allowed_root not in artifact_path.parents:
            raise HTTPException(status_code=403, detail="Artifact path is outside allowed job artifact directory.")

        if not artifact_path.exists() or not artifact_path.is_file():
            raise HTTPException(status_code=404, detail="Artifact file is missing from storage.")

        return artifact_path, artifact.content_type

    def trigger_repair(self, job_id: str) -> JobStatusResponse:
        self.logger.info("Trigger repair requested", extra={"event": "job_repair_trigger", "job_id": job_id})
        with self._lock:
            with SessionLocal() as session:
                repository = JobRepository(session)
                snapshot = repository.get_job_snapshot(job_id)

                if snapshot.status == JobStatusDb.DONE:
                    return JobStatusResponse(
                        job_id=snapshot.job_id,
                        status=JobStatus(snapshot.status.value),
                        progress=snapshot.progress,
                        current_step=snapshot.current_step,
                        error=snapshot.error_message,
                    )

                if snapshot.status != JobStatusDb.READY_FOR_REPAIR:
                    raise HTTPException(status_code=409, detail="Job is not ready for repair.")

                self._transition(
                    repository=repository,
                    job_id=job_id,
                    next_status=JobStatusDb.REPAIRING,
                    progress=70,
                    current_step="repair_queued",
                )
                session.commit()

            self.dispatch_repair_pipeline(job_id=job_id)
        self.logger.info("Repair dispatched", extra={"event": "job_repair_dispatched", "job_id": job_id})
        return self.get_job_status(job_id)

    def dispatch_analysis_pipeline(self, job_id: str, auto_repair: bool) -> None:
        self.cloud_manager.submit_job(
            {
                "job_id": job_id,
                "action": "analyze",
                "auto_repair": auto_repair,
            }
        )

    def dispatch_repair_pipeline(self, job_id: str) -> None:
        self.cloud_manager.submit_job(
            {
                "job_id": job_id,
                "action": "repair",
            }
        )

    def reset_state_for_tests(self) -> None:
        init_db()
        with SessionLocal() as session:
            repository = JobRepository(session)
            repository.clear_all()
            session.commit()

    def _transition(
        self,
        repository: JobRepository,
        job_id: str,
        next_status: JobStatusDb,
        progress: int,
        current_step: str,
    ) -> None:
        snapshot = repository.get_job_snapshot(job_id)
        allowed = self._allowed_transitions.get(snapshot.status, set())
        if next_status not in allowed:
            raise HTTPException(
                status_code=409,
                detail=f"Invalid job transition: {snapshot.status.value} -> {next_status.value}",
            )

        self.logger.info(
            "Job state transition",
            extra={"event": "job_state_transition", "job_id": job_id, "status": next_status.value},
        )
        repository.update_job_state(
            job_id=job_id,
            status=next_status,
            progress=progress,
            current_step=current_step,
        )

    def _mark_failed(self, job_id: str, step: str, message: str) -> None:
        self.logger.error(
            "Marking job failed",
            extra={"event": "job_mark_failed", "job_id": job_id, "status": "FAILED"},
        )
        with self._lock:
            with SessionLocal() as session:
                repository = JobRepository(session)
                snapshot = repository.get_job_snapshot(job_id)
                allowed = self._allowed_transitions.get(snapshot.status, set())
                if JobStatusDb.FAILED in allowed:
                    repository.update_job_state(
                        job_id=job_id,
                        status=JobStatusDb.FAILED,
                        progress=100,
                        current_step=step,
                        error_message=message,
                        error_code="PIPELINE_ERROR",
                    )
                    session.commit()

    def _attach_snippets(
        self,
        findings: list[Finding],
        repository_id: str,
        source_type: str,
        phase: str,
        storage_key: str | None = None,
        github_url: str | None = None,
        context: int = 3,
    ) -> None:
        file_cache: dict[str, list[str] | None] = {}

        for finding in findings:
            if not finding.file or finding.line <= 0:
                continue

            if finding.file not in file_cache:
                try:
                    file_cache[finding.file] = self.analyzer_runner.read_source_file(
                        repository_id=repository_id,
                        source_type=source_type,
                        file_path=finding.file,
                        phase=phase,
                        storage_key=storage_key,
                        github_url=github_url,
                    )
                except HTTPException:
                    file_cache[finding.file] = None

            source_lines = file_cache.get(finding.file)
            if not source_lines:
                continue

            idx = max(0, finding.line - 1)
            start = max(0, idx - context)
            end = min(len(source_lines), idx + context + 1)

            finding.snippet = source_lines[start:end]
            finding.snippet_start = start + 1

    @staticmethod
    def _build_summary(before: list[Finding], after: list[Finding]) -> JobSummary:
        before_total = len(before)
        after_total = len(after)
        if before_total == 0:
            reduction_pct = 0.0
        else:
            reduction_pct = round(((before_total - after_total) / before_total) * 100, 2)
        return JobSummary(before_total=before_total, after_total=after_total, reduction_pct=reduction_pct)
