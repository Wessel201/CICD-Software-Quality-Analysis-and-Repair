from threading import Lock
from uuid import uuid4

from fastapi import HTTPException

from app.db.models import AnalysisPhase, JobStatusDb
from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.repositories.job_repository import JobRepository
from app.schemas.job import Finding, JobCreateResponse, JobResultsResponse, JobStatus, JobStatusResponse, JobSummary, PatchInfo


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

    def create_job(self, source_type: str, source_reference: str, auto_repair: bool) -> JobCreateResponse:
        job_id = f"job_{uuid4().hex[:12]}"
        created_at = None

        with self._lock:
            with SessionLocal() as session:
                repository = JobRepository(session)
                repository.upsert_repository(repository_id=source_reference, source_type=source_type)
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

    def get_job_results(self, job_id: str) -> JobResultsResponse:
        with SessionLocal() as session:
            repository = JobRepository(session)
            snapshot = repository.get_job_snapshot(job_id)
            before = repository.get_findings_for_phase(job_id=job_id, phase=AnalysisPhase.BEFORE)
            after = repository.get_findings_for_phase(job_id=job_id, phase=AnalysisPhase.AFTER)
            patches = repository.get_patches(job_id=job_id)

            if not before:
                raise HTTPException(status_code=409, detail="Analysis results are not available yet.")

            if snapshot.status != JobStatusDb.DONE and not after:
                raise HTTPException(status_code=409, detail="Repair results are not available yet.")

            summary = self._build_summary(before, after)
            return JobResultsResponse(
                job_id=job_id,
                summary=summary,
                before=before,
                after=after,
                patches=patches,
            )

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
        try:
            from app.workers.job_tasks import run_analysis_pipeline_task

            run_analysis_pipeline_task.delay(job_id=job_id, auto_repair=auto_repair)
        except Exception:
            self.run_analysis_pipeline(job_id=job_id, auto_repair=auto_repair)

    def dispatch_repair_pipeline(self, job_id: str, repair_strategy: str) -> None:
        try:
            from app.workers.job_tasks import run_repair_pipeline_task

            run_repair_pipeline_task.delay(job_id=job_id, repair_strategy=repair_strategy)
        except Exception:
            self.run_repair_pipeline(job_id=job_id, repair_strategy=repair_strategy)

    def run_analysis_pipeline(self, job_id: str, auto_repair: bool) -> None:
        with self._lock:
            with SessionLocal() as session:
                repository = JobRepository(session)
                self._transition(repository, job_id, JobStatusDb.FETCHING, 15, "fetching_source")
                self._transition(repository, job_id, JobStatusDb.ANALYZING, 50, "running_static_analysis")

                before_findings = [
                    Finding(
                        tool="bandit",
                        rule_id="B105",
                        severity="high",
                        category="security",
                        file="app/auth.py",
                        line=14,
                        message="Possible hardcoded password string.",
                        suggestion="Use environment-based secret management.",
                    ),
                    Finding(
                        tool="ruff",
                        rule_id="F401",
                        severity="low",
                        category="code_smell",
                        file="app/main.py",
                        line=2,
                        message="Imported but unused name.",
                        suggestion="Remove unused imports.",
                    ),
                    Finding(
                        tool="radon",
                        rule_id="CC",
                        severity="medium",
                        category="complexity",
                        file="app/service.py",
                        line=30,
                        message="Cyclomatic complexity is too high (13).",
                        suggestion="Split logic into smaller functions.",
                    ),
                ]
                repository.replace_findings_for_phase(job_id=job_id, phase=AnalysisPhase.BEFORE, findings=before_findings)

                self._transition(repository, job_id, JobStatusDb.READY_FOR_REPAIR, 65, "analysis_completed")
                session.commit()

        if auto_repair:
            self.run_repair_pipeline(job_id=job_id, repair_strategy="balanced")

    def run_repair_pipeline(self, job_id: str, repair_strategy: str = "balanced") -> None:
        with self._lock:
            with SessionLocal() as session:
                repository = JobRepository(session)
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

                after_findings = [
                    Finding(
                        tool="radon",
                        rule_id="CC",
                        severity="low",
                        category="complexity",
                        file="app/service.py",
                        line=30,
                        message="Cyclomatic complexity reduced to 7.",
                        suggestion="Continue decomposition if needed.",
                    )
                ]
                patches = [
                    PatchInfo(
                        file="app/service.py",
                        diff_url=f"artifacts://{job_id}/patches/app_service.patch",
                    )
                ]

                repository.replace_findings_for_phase(job_id=job_id, phase=AnalysisPhase.AFTER, findings=after_findings)
                repository.replace_patches(job_id=job_id, patches=patches)

                self._transition(repository, job_id, JobStatusDb.DONE, 100, "completed")
                session.commit()

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

    @staticmethod
    def _build_summary(before: list[Finding], after: list[Finding]) -> JobSummary:
        before_total = len(before)
        after_total = len(after)
        if before_total == 0:
            reduction_pct = 0.0
        else:
            reduction_pct = round(((before_total - after_total) / before_total) * 100, 2)
        return JobSummary(before_total=before_total, after_total=after_total, reduction_pct=reduction_pct)
