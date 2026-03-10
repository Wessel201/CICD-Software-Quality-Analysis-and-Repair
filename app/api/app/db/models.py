from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Enum as SqlEnum, ForeignKey, Index, Integer, JSON, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class SourceType(str, Enum):
    GITHUB_URL = "github_url"
    UPLOAD = "upload"


class JobStatusDb(str, Enum):
    QUEUED = "QUEUED"
    FETCHING = "FETCHING"
    ANALYZING = "ANALYZING"
    READY_FOR_REPAIR = "READY_FOR_REPAIR"
    REPAIRING = "REPAIRING"
    REANALYZING = "REANALYZING"
    DONE = "DONE"
    FAILED = "FAILED"


class AnalysisPhase(str, Enum):
    BEFORE = "before"
    AFTER = "after"


class RepositoryModel(Base):
    __tablename__ = "repositories"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_type: Mapped[SourceType] = mapped_column(SqlEnum(SourceType, name="source_type_enum"), nullable=False)
    github_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    storage_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    revision: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    jobs: Mapped[list["JobModel"]] = relationship(back_populates="repository")


class JobModel(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint("progress >= 0 AND progress <= 100", name="ck_jobs_progress_range"),
        Index("ix_jobs_status_created_at", "status", "created_at"),
        Index("ix_jobs_repository_id", "repository_id"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    repository_id: Mapped[str] = mapped_column(String(64), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[JobStatusDb] = mapped_column(SqlEnum(JobStatusDb, name="job_status_enum"), nullable=False)
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    auto_repair: Mapped[bool] = mapped_column(nullable=False, default=False)
    current_step: Mapped[str] = mapped_column(String(128), nullable=False, default="queued")
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    repository: Mapped[RepositoryModel] = relationship(back_populates="jobs")
    analysis_runs: Mapped[list["AnalysisRunModel"]] = relationship(back_populates="job")
    artifacts: Mapped[list["ArtifactModel"]] = relationship(back_populates="job")


class AnalysisRunModel(Base):
    __tablename__ = "analysis_runs"
    __table_args__ = (Index("ix_analysis_runs_job_phase", "job_id", "phase"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job_id: Mapped[str] = mapped_column(String(32), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    phase: Mapped[AnalysisPhase] = mapped_column(SqlEnum(AnalysisPhase, name="analysis_phase_enum"), nullable=False)
    summary_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    job: Mapped[JobModel] = relationship(back_populates="analysis_runs")
    findings: Mapped[list["FindingModel"]] = relationship(back_populates="analysis_run")


class FindingModel(Base):
    __tablename__ = "findings"
    __table_args__ = (
        Index("ix_findings_run_tool_severity", "analysis_run_id", "tool", "severity"),
        Index("ix_findings_fingerprint", "fingerprint"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_run_id: Mapped[str] = mapped_column(String(36), ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False)
    tool: Mapped[str] = mapped_column(String(64), nullable=False)
    rule_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    file_path: Mapped[str] = mapped_column(String(2048), nullable=False)
    line: Mapped[int | None] = mapped_column(Integer, nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    suggestion: Mapped[str | None] = mapped_column(Text, nullable=True)
    fingerprint: Mapped[str | None] = mapped_column(String(128), nullable=True)

    analysis_run: Mapped[AnalysisRunModel] = relationship(back_populates="findings")


class ArtifactModel(Base):
    __tablename__ = "artifacts"
    __table_args__ = (Index("ix_artifacts_job_type", "job_id", "type"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(String(32), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    job: Mapped[JobModel] = relationship(back_populates="artifacts")
