from dataclasses import dataclass
from threading import Lock
from typing import ClassVar
from uuid import uuid4

from fastapi import HTTPException

from app.schemas.job import (
    Finding,
    JobCreateResponse,
    JobResultsResponse,
    JobStatus,
    JobStatusResponse,
    JobSummary,
    PatchInfo,
    utc_now,
)


@dataclass
class JobRecord:
    job_id: str
    status: JobStatus
    progress: int
    current_step: str
    error: str | None
    created_at_iso: str
    source_type: str
    source_reference: str
    before: list[Finding]
    after: list[Finding]
    patches: list[PatchInfo]


class JobService:
    _jobs: ClassVar[dict[str, JobRecord]] = {}
    _lock: ClassVar[Lock] = Lock()

    def __init__(self) -> None:
        pass

    def create_job(self, source_type: str, source_reference: str, auto_repair: bool) -> JobCreateResponse:
        created_at = utc_now()
        job_id = f"job_{uuid4().hex[:12]}"

        with self._lock:
            record = JobRecord(
                job_id=job_id,
                status=JobStatus.QUEUED,
                progress=0,
                current_step="queued",
                error=None,
                created_at_iso=created_at.isoformat(),
                source_type=source_type,
                source_reference=source_reference,
                before=[],
                after=[],
                patches=[],
            )
            self._jobs[job_id] = record

        self.dispatch_analysis_pipeline(job_id=job_id, auto_repair=auto_repair)

        current_record = self._get_job(job_id)

        return JobCreateResponse(job_id=job_id, status=current_record.status, created_at=created_at)

    def get_job_status(self, job_id: str) -> JobStatusResponse:
        record = self._get_job(job_id)
        return JobStatusResponse(
            job_id=record.job_id,
            status=record.status,
            progress=record.progress,
            current_step=record.current_step,
            error=record.error,
        )

    def get_job_results(self, job_id: str) -> JobResultsResponse:
        record = self._get_job(job_id)

        if not record.before:
            raise HTTPException(status_code=409, detail="Analysis results are not available yet.")

        if record.status != JobStatus.DONE and not record.after:
            raise HTTPException(status_code=409, detail="Repair results are not available yet.")

        summary = self._build_summary(record.before, record.after)
        return JobResultsResponse(
            job_id=record.job_id,
            summary=summary,
            before=record.before,
            after=record.after,
            patches=record.patches,
        )

    def trigger_repair(self, job_id: str, repair_strategy: str) -> JobStatusResponse:
        with self._lock:
            record = self._get_job(job_id)
            if record.status == JobStatus.DONE:
                return self.get_job_status(job_id)

            if record.status != JobStatus.READY_FOR_REPAIR:
                raise HTTPException(status_code=409, detail="Job is not ready for repair.")

            record.status = JobStatus.REPAIRING
            record.progress = 70
            record.current_step = "repair_queued"

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
            record = self._get_job(job_id)
            record.status = JobStatus.FETCHING
            record.progress = 15
            record.current_step = "fetching_source"

            record.status = JobStatus.ANALYZING
            record.progress = 50
            record.current_step = "running_static_analysis"
            record.before = [
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

            record.status = JobStatus.READY_FOR_REPAIR
            record.progress = 65
            record.current_step = "analysis_completed"

        if auto_repair:
            self.run_repair_pipeline(job_id=job_id, repair_strategy="balanced")

    def run_repair_pipeline(self, job_id: str, repair_strategy: str = "balanced") -> None:
        with self._lock:
            record = self._get_job(job_id)
            record.status = JobStatus.REPAIRING
            record.progress = 80
            record.current_step = f"applying_llm_repair_{repair_strategy}"

            record.status = JobStatus.REANALYZING
            record.progress = 92
            record.current_step = "re_running_static_analysis"

            record.after = [
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
            record.patches = [
                PatchInfo(
                    file="app/service.py",
                    diff_url=f"artifacts://{record.job_id}/patches/app_service.patch",
                )
            ]

            record.status = JobStatus.DONE
            record.progress = 100
            record.current_step = "completed"

    def _get_job(self, job_id: str) -> JobRecord:
        record = self._jobs.get(job_id)
        if not record:
            raise HTTPException(status_code=404, detail="Job not found.")
        return record

    @staticmethod
    def _build_summary(before: list[Finding], after: list[Finding]) -> JobSummary:
        before_total = len(before)
        after_total = len(after)
        if before_total == 0:
            reduction_pct = 0.0
        else:
            reduction_pct = round(((before_total - after_total) / before_total) * 100, 2)
        return JobSummary(before_total=before_total, after_total=after_total, reduction_pct=reduction_pct)
