"""create job centric schema

Revision ID: 0001_job_centric_schema
Revises:
Create Date: 2026-03-01
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_job_centric_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    source_type_enum = sa.Enum("github_url", "upload", name="source_type_enum")
    job_status_enum = sa.Enum(
        "QUEUED",
        "FETCHING",
        "ANALYZING",
        "READY_FOR_REPAIR",
        "REPAIRING",
        "REANALYZING",
        "DONE",
        "FAILED",
        name="job_status_enum",
    )
    analysis_phase_enum = sa.Enum("before", "after", name="analysis_phase_enum")

    bind = op.get_bind()
    source_type_enum.create(bind, checkfirst=True)
    job_status_enum.create(bind, checkfirst=True)
    analysis_phase_enum.create(bind, checkfirst=True)

    op.create_table(
        "repositories",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("source_type", source_type_enum, nullable=False),
        sa.Column("github_url", sa.String(length=2048), nullable=True),
        sa.Column("storage_key", sa.String(length=1024), nullable=True),
        sa.Column("revision", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "jobs",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("repository_id", sa.String(length=64), nullable=False),
        sa.Column("status", job_status_enum, nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("auto_repair", sa.Boolean(), nullable=False),
        sa.Column("current_step", sa.String(length=128), nullable=False),
        sa.Column("error_code", sa.String(length=128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("progress >= 0 AND progress <= 100", name="ck_jobs_progress_range"),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_jobs_status_created_at", "jobs", ["status", "created_at"], unique=False)
    op.create_index("ix_jobs_repository_id", "jobs", ["repository_id"], unique=False)

    op.create_table(
        "analysis_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("job_id", sa.String(length=32), nullable=False),
        sa.Column("phase", analysis_phase_enum, nullable=False),
        sa.Column("summary_json", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_analysis_runs_job_phase", "analysis_runs", ["job_id", "phase"], unique=False)

    op.create_table(
        "findings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("analysis_run_id", sa.String(length=36), nullable=False),
        sa.Column("tool", sa.String(length=64), nullable=False),
        sa.Column("rule_id", sa.String(length=128), nullable=True),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("category", sa.String(length=128), nullable=True),
        sa.Column("file_path", sa.String(length=2048), nullable=False),
        sa.Column("line", sa.Integer(), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("suggestion", sa.Text(), nullable=True),
        sa.Column("fingerprint", sa.String(length=128), nullable=True),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_findings_run_tool_severity", "findings", ["analysis_run_id", "tool", "severity"], unique=False)
    op.create_index("ix_findings_fingerprint", "findings", ["fingerprint"], unique=False)

    op.create_table(
        "artifacts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.String(length=32), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("storage_key", sa.String(length=1024), nullable=False),
        sa.Column("content_type", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_artifacts_job_type", "artifacts", ["job_id", "type"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_artifacts_job_type", table_name="artifacts")
    op.drop_table("artifacts")

    op.drop_index("ix_findings_fingerprint", table_name="findings")
    op.drop_index("ix_findings_run_tool_severity", table_name="findings")
    op.drop_table("findings")

    op.drop_index("ix_analysis_runs_job_phase", table_name="analysis_runs")
    op.drop_table("analysis_runs")

    op.drop_index("ix_jobs_repository_id", table_name="jobs")
    op.drop_index("ix_jobs_status_created_at", table_name="jobs")
    op.drop_table("jobs")

    op.drop_table("repositories")

    bind = op.get_bind()
    sa.Enum(name="analysis_phase_enum").drop(bind, checkfirst=True)
    sa.Enum(name="job_status_enum").drop(bind, checkfirst=True)
    sa.Enum(name="source_type_enum").drop(bind, checkfirst=True)
