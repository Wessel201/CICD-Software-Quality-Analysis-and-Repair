from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    QUEUED = "QUEUED"
    FETCHING = "FETCHING"
    ANALYZING = "ANALYZING"
    READY_FOR_REPAIR = "READY_FOR_REPAIR"
    REPAIRING = "REPAIRING"
    REANALYZING = "REANALYZING"
    DONE = "DONE"
    FAILED = "FAILED"


class Finding(BaseModel):
    tool: str
    rule_id: str
    severity: Literal["low", "medium", "high", "critical"]
    category: str
    file: str
    line: int
    message: str
    suggestion: str
    # Lines of source code surrounding the finding (populated at analysis time)
    snippet: list[str] = []
    snippet_start: int = 0  # 1-based line number of snippet[0]


class JobSummary(BaseModel):
    before_total: int
    after_total: int
    reduction_pct: float


class PatchInfo(BaseModel):
    file: str
    diff_url: str


class JobCreateResponse(BaseModel):
    job_id: str
    status: JobStatus
    created_at: datetime


class JobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    progress: int = Field(ge=0, le=100)
    current_step: str
    error: str | None


class JobResultsResponse(BaseModel):
    job_id: str
    summary: JobSummary
    before: list[Finding]
    after: list[Finding]
    patches: list[PatchInfo]


class ArtifactInfo(BaseModel):
    artifact_id: int | None = None
    artifact_type: str
    storage_key: str
    content_type: str | None


class JobArtifactsResponse(BaseModel):
    job_id: str
    artifacts: list[ArtifactInfo]


class JobRepairRequest(BaseModel):
    repair_strategy: Literal["balanced", "aggressive", "safe"] = "balanced"


class ErrorBody(BaseModel):
    code: str
    message: str = ""
    details: dict[str, str] = Field(default_factory=dict)


class SourceFileResponse(BaseModel):
    file: str
    lines: list[str]
    total: int

class JobListItem(BaseModel):
    job_id: str
    status: JobStatus
    created_at: datetime
    finished_at: datetime | None = None
    source_label: str | None = None
    """Human-readable source name: repo name for GitHub URLs, filename for uploads."""


class JobListResponse(BaseModel):
    jobs: list[JobListItem]

class ErrorResponse(BaseModel):
    error: ErrorBody


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
