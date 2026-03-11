from threading import Lock
from uuid import uuid4
import os
from pathlib import Path
import json

from fastapi import HTTPException

from app.db.models import AnalysisPhase, JobStatusDb
from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.repositories.job_repository import JobRepository
from app.services.analyzer_runner import AnalyzerRunner
from app.schemas.job import Finding, JobCreateResponse, JobListItem, JobListResponse, JobResultsResponse, JobStatus, JobStatusResponse, JobSummary, PatchInfo
from app.schemas.job import ArtifactInfo, JobArtifactsResponse, SourceFileResponse


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

    def create_job(self, source_type: str, source_reference: str, auto_repair: bool, github_url: str | None = None) -> JobCreateResponse:
        job_id = f"job_{uuid4().hex[:12]}"
        created_at = None

        with self._lock:
            with SessionLocal() as session:
                repository = JobRepository(session)
                repository.upsert_repository(repository_id=source_reference, source_type=source_type, github_url=github_url)
                job = repository.create_job(job_id=job_id, repository_id=source_reference, auto_repair=auto_repair)
                created_at = job.created_at
                session.commit()

        self.dispatch_analysis_pipeline(job_id=job_id, auto_repair=auto_repair)

        current_status = self.get_job_status(job_id)

        if created_at is None:
            raise HTTPException(status_code=500, detail="Failed to persist job creation timestamp.")

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
        with self._lock:
            with SessionLocal() as session:
                repository = JobRepository(session)
                repository.delete_job(job_id)
                session.commit()

    def list_recent_jobs(self, limit: int = 50) -> JobListResponse:
        with SessionLocal() as session:
            repository = JobRepository(session)
            snapshots = repository.list_recent_jobs(limit=limit)

        jobs: list[JobListItem] = []
        for s in snapshots:
            # For upload jobs, storage_key is the UUID — try to find the real filename on disk
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

            if not before:
                raise HTTPException(status_code=409, detail="Analysis results are not available yet.")

            # Don't gate on 'after' — it's empty when repair hasn't run yet (READY_FOR_REPAIR)
            summary = self._build_summary(before, after)
            return JobResultsResponse(
                job_id=job_id,
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
        )
        filename = f"{job_id}_{phase}_source.zip"
        return zip_bytes, filename

    def get_job_artifact_download(self, job_id: str, artifact_id: int) -> tuple[Path, str | None]:
        with SessionLocal() as session:
            repository = JobRepository(session)
            repository.get_job_snapshot(job_id)
            artifact = repository.get_artifact_for_job(job_id=job_id, artifact_id=artifact_id)

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

    def trigger_repair(self, job_id: str, repair_strategy: str) -> JobStatusResponse:
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

        self.dispatch_repair_pipeline(job_id=job_id, repair_strategy=repair_strategy)
        return self.get_job_status(job_id)

    def dispatch_analysis_pipeline(self, job_id: str, auto_repair: bool) -> None:
        if os.getenv("CELERY_TASK_ALWAYS_EAGER", "true").lower() == "true":
            self.run_analysis_pipeline(job_id=job_id, auto_repair=auto_repair)
            return

        try:
            from app.workers.job_tasks import run_analysis_pipeline_task

            run_analysis_pipeline_task.delay(job_id=job_id, auto_repair=auto_repair)
        except Exception:
            self.run_analysis_pipeline(job_id=job_id, auto_repair=auto_repair)

    def dispatch_repair_pipeline(self, job_id: str, repair_strategy: str) -> None:
        if os.getenv("CELERY_TASK_ALWAYS_EAGER", "true").lower() == "true":
            self.run_repair_pipeline(job_id=job_id, repair_strategy=repair_strategy)
            return

        try:
            from app.workers.job_tasks import run_repair_pipeline_task

            run_repair_pipeline_task.delay(job_id=job_id, repair_strategy=repair_strategy)
        except Exception:
            self.run_repair_pipeline(job_id=job_id, repair_strategy=repair_strategy)

    def run_analysis_pipeline(self, job_id: str, auto_repair: bool) -> None:
        try:
            with self._lock:
                with SessionLocal() as session:
                    repository = JobRepository(session)
                    job_context = repository.get_job_context(job_id)

                    self._transition(repository, job_id, JobStatusDb.FETCHING, 15, "fetching_source")
                    self._transition(repository, job_id, JobStatusDb.ANALYZING, 50, "running_static_analysis")

                    before_findings, before_reports = self.analyzer_runner.analyze_repository_with_reports(
                        repository_id=job_context.repository_id,
                        source_type=job_context.source_type,
                        phase="before",
                    )
                    repository.replace_findings_for_phase(job_id=job_id, phase=AnalysisPhase.BEFORE, findings=before_findings)
                    analysis_artifacts = self._write_analysis_artifacts(
                        job_id=job_id,
                        stage="analysis",
                        artifact_type="analysis_report",
                        reports=before_reports,
                    )
                    if analysis_artifacts:
                        repository.replace_artifacts_by_type(
                            job_id=job_id,
                            artifact_type="analysis_report",
                            artifacts=analysis_artifacts,
                        )

                    self._transition(repository, job_id, JobStatusDb.READY_FOR_REPAIR, 65, "analysis_completed")
                    session.commit()
        except Exception as exc:
            self._mark_failed(job_id=job_id, step="analysis_failed", message=str(exc))
            return

        if auto_repair:
            self.run_repair_pipeline(job_id=job_id, repair_strategy="balanced")

    def run_repair_pipeline(self, job_id: str, repair_strategy: str = "balanced") -> None:
        try:
            with self._lock:
                with SessionLocal() as session:
                    repository = JobRepository(session)
                    job_context = repository.get_job_context(job_id)
                    snapshot = repository.get_job_snapshot(job_id)
                    if snapshot.status == JobStatusDb.DONE:
                        return

                    if snapshot.status != JobStatusDb.REPAIRING:
                        self._transition(repository, job_id, JobStatusDb.REPAIRING, 80, f"applying_llm_repair_{repair_strategy}")
                    else:
                        repository.update_job_state(
                            job_id,
                            status=JobStatusDb.REPAIRING,
                            progress=80,
                            current_step=f"applying_llm_repair_{repair_strategy}",
                        )

                    self._transition(repository, job_id, JobStatusDb.REANALYZING, 92, "re_running_static_analysis")

                    after_findings, after_reports = self.analyzer_runner.analyze_repository_with_reports(
                        repository_id=job_context.repository_id,
                        source_type=job_context.source_type,
                        phase="after",
                    )
                    patches = [
                        PatchInfo(
                            file="app/service.py",
                            diff_url=f"artifacts://{job_id}/patches/app_service.patch",
                        )
                    ]

                    repository.replace_findings_for_phase(job_id=job_id, phase=AnalysisPhase.AFTER, findings=after_findings)
                    repository.replace_patches(job_id=job_id, patches=patches)
                    repair_artifacts = self._write_analysis_artifacts(
                        job_id=job_id,
                        stage="repair",
                        artifact_type="analysis_report_after",
                        reports=after_reports,
                    )
                    if repair_artifacts:
                        repository.replace_artifacts_by_type(
                            job_id=job_id,
                            artifact_type="analysis_report_after",
                            artifacts=repair_artifacts,
                        )

                    self._transition(repository, job_id, JobStatusDb.DONE, 100, "completed")
                    session.commit()
        except Exception as exc:
            self._mark_failed(job_id=job_id, step="repair_failed", message=str(exc))

    def _write_analysis_artifacts(
        self,
        job_id: str,
        stage: str,
        artifact_type: str,
        reports: dict[str, object],
    ) -> list[ArtifactInfo]:
        artifacts_dir = Path("uploads") / job_id / "artifacts" / stage
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        artifacts: list[ArtifactInfo] = []
        for tool, payload in reports.items():
            artifact_file = artifacts_dir / f"{tool}.json"
            artifact_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            artifacts.append(
                ArtifactInfo(
                    artifact_type=artifact_type,
                    storage_key=artifact_file.as_posix(),
                    content_type="application/json",
                )
            )

        return artifacts

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

        repository.update_job_state(
            job_id=job_id,
            status=next_status,
            progress=progress,
            current_step=current_step,
        )

    def _mark_failed(self, job_id: str, step: str, message: str) -> None:
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

    @staticmethod
    def _build_summary(before: list[Finding], after: list[Finding]) -> JobSummary:
        before_total = len(before)
        after_total = len(after)
        if before_total == 0:
            reduction_pct = 0.0
        else:
            reduction_pct = round(((before_total - after_total) / before_total) * 100, 2)
        return JobSummary(before_total=before_total, after_total=after_total, reduction_pct=reduction_pct)
