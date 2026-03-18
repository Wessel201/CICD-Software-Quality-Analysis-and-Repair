import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any
from zipfile import ZipFile

import boto3
import psycopg

from analyzer import Analyzer


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "service": "worker",
            "event": getattr(record, "event", "log"),
            "message": record.getMessage(),
        }

        for field in ["job_id", "message_id", "status", "duration_ms"]:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(payload)


def configure_logging() -> None:
    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root_logger.addHandler(handler)
    root_logger.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())


configure_logging()
logger = logging.getLogger(__name__)


def _build_database_url() -> str:
    explicit_url = os.getenv("DATABASE_URL")
    if explicit_url:
        return explicit_url

    db_host = os.getenv("DB_HOST")
    db_name = os.getenv("DB_NAME", "codequality")
    db_user = os.getenv("DB_USER", "postgres_admin")
    db_password = os.getenv("DB_PASSWORD", "")
    db_port = os.getenv("DB_PORT", "5432")

    if not db_host:
        raise RuntimeError("DB_HOST or DATABASE_URL must be configured.")
    if db_password:
        return f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    return f"postgresql://{db_user}@{db_host}:{db_port}/{db_name}"


class SqsWorker:
    def __init__(self) -> None:
        self.queue_url = os.getenv("SQS_QUEUE_URL")
        self.bucket_name = os.getenv("S3_BUCKET_NAME")
        self.aws_region = os.getenv("AWS_REGION", "eu-central-1")
        self.database_url = _build_database_url()

        if not self.queue_url:
            raise RuntimeError("SQS_QUEUE_URL must be configured.")
        if not self.bucket_name:
            raise RuntimeError("S3_BUCKET_NAME must be configured.")

        self.sqs = boto3.client("sqs", region_name=self.aws_region)
        self.s3 = boto3.client("s3", region_name=self.aws_region)
        self.max_repair_cycles = self._parse_max_repair_cycles(os.getenv("MAX_REPAIR_CYCLES", "3"))

    def run_forever(self) -> None:
        logger.info("Worker started", extra={"event": "worker_started"})
        while True:
            message = self._receive_message()
            if message is None:
                continue

            receipt = message["ReceiptHandle"]
            message_id = message.get("MessageId", "unknown")
            try:
                payload = json.loads(message.get("Body", "{}"))
                logger.info(
                    "Processing message",
                    extra={"event": "message_processing_start", "message_id": message_id, "job_id": payload.get("job_id")},
                )
                self._process_payload(payload)
                self._delete_message(receipt)
                logger.info(
                    "Finished message",
                    extra={"event": "message_processing_complete", "message_id": message_id, "job_id": payload.get("job_id")},
                )
            except Exception as exc:
                # Do not delete message. SQS retry + DLQ policy handles failures.
                logger.exception(
                    "Message processing failed",
                    extra={"event": "message_processing_failed", "message_id": message_id},
                )
                time.sleep(1)

    def _receive_message(self) -> dict[str, Any] | None:
        response = self.sqs.receive_message(
            QueueUrl=self.queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=20,
            VisibilityTimeout=600,
        )
        messages = response.get("Messages", [])
        return messages[0] if messages else None

    def _delete_message(self, receipt_handle: str) -> None:
        self.sqs.delete_message(QueueUrl=self.queue_url, ReceiptHandle=receipt_handle)

    def _process_payload(self, payload: dict[str, Any]) -> None:
        job_id = str(payload.get("job_id", "")).strip()
        if not job_id:
            raise RuntimeError("Message payload missing job_id.")

        action = str(payload.get("action", "analyze")).lower()
        logger.info("Payload received", extra={"event": "payload_received", "job_id": job_id})
        with psycopg.connect(self.database_url) as conn:
            conn.autocommit = False
            context = self._get_job_context(conn, job_id)
            requested_cycles = payload.get("max_repair_cycles")

            if action == "repair":
                self._run_repair_pipeline(conn, context, requested_cycles=requested_cycles)
            else:
                self._run_analysis_pipeline(conn, context, payload)

            conn.commit()

    def _get_job_context(self, conn: psycopg.Connection, job_id: str) -> dict[str, Any]:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    j.id,
                    j.status,
                    j.auto_repair,
                    r.id AS repository_id,
                    r.source_type::text,
                    r.github_url,
                    r.storage_key
                FROM jobs j
                JOIN repositories r ON r.id = j.repository_id
                WHERE j.id = %s
                """,
                (job_id,),
            )
            row = cur.fetchone()

        if row is None:
            raise RuntimeError(f"Job {job_id} not found.")

        return {
            "job_id": row[0],
            "status": row[1],
            "auto_repair": bool(row[2]),
            "repository_id": row[3],
            "source_type": row[4],
            "github_url": row[5],
            "storage_key": row[6],
        }

    def _run_analysis_pipeline(self, conn: psycopg.Connection, context: dict[str, Any], payload: dict[str, Any]) -> None:
        job_id = context["job_id"]
        auto_repair = bool(payload.get("auto_repair", context["auto_repair"]))
        logger.info("Analysis pipeline started", extra={"event": "analysis_start", "job_id": job_id})

        self._update_job_state(conn, job_id, "FETCHING", 15, "fetching_source")
        source_dir, cleanup_path = self._prepare_source(context)
        try:
            self._update_job_state(conn, job_id, "ANALYZING", 50, "running_static_analysis")
            analysis = Analyzer(str(source_dir)).run_all()
            before_findings = self._normalize_findings(analysis)
            self._replace_findings(conn, job_id, "before", before_findings)

            if auto_repair:
                self._run_repair_pipeline(
                    conn,
                    context,
                    source_dir=source_dir,
                    requested_cycles=payload.get("max_repair_cycles"),
                )
            else:
                self._update_job_state(conn, job_id, "READY_FOR_REPAIR", 65, "analysis_completed")
                logger.info("Analysis completed", extra={"event": "analysis_complete", "job_id": job_id, "status": "READY_FOR_REPAIR"})
        except Exception as exc:
            logger.exception("Analysis pipeline failed", extra={"event": "analysis_failed", "job_id": job_id})
            conn.rollback()
            self._mark_failed(conn, job_id, "analysis_failed", str(exc))
            conn.commit()
            raise
        finally:
            shutil.rmtree(cleanup_path, ignore_errors=True)

    def _run_repair_pipeline(
        self,
        conn: psycopg.Connection,
        context: dict[str, Any],
        source_dir: Path | None = None,
        requested_cycles: Any = None,
    ) -> None:
        job_id = context["job_id"]
        created_locally = False
        repair_cycles = self._bounded_repair_cycles(requested_cycles)
        logger.info("Repair pipeline started", extra={"event": "repair_start", "job_id": job_id})

        if source_dir is None:
            source_dir, cleanup_path = self._prepare_source(context)
            created_locally = True
        else:
            cleanup_path = source_dir.parent

        try:
            after_findings: list[dict[str, Any]] = []
            for cycle in range(1, repair_cycles + 1):
                logger.info(
                    "Repair cycle started",
                    extra={"event": "repair_cycle_start", "job_id": job_id},
                )
                self._update_job_state(
                    conn,
                    job_id,
                    "REPAIRING",
                    80,
                    f"applying_llm_repair_balanced_cycle_{cycle}_of_{repair_cycles}",
                )
                # Placeholder repair: keep source unchanged, run post-repair analysis for consistent API shape.
                self._update_job_state(
                    conn,
                    job_id,
                    "REANALYZING",
                    92,
                    f"re_running_static_analysis_cycle_{cycle}_of_{repair_cycles}",
                )
                after_analysis = Analyzer(str(source_dir)).run_all()
                after_findings = self._normalize_findings(after_analysis)
                self._replace_findings(conn, job_id, "after", after_findings)

                if not after_findings:
                    break

            self._update_job_state(conn, job_id, "DONE", 100, "completed")
            logger.info("Repair pipeline completed", extra={"event": "repair_complete", "job_id": job_id, "status": "DONE"})
        except Exception as exc:
            logger.exception("Repair pipeline failed", extra={"event": "repair_failed", "job_id": job_id})
            conn.rollback()
            self._mark_failed(conn, job_id, "repair_failed", str(exc))
            conn.commit()
            raise
        finally:
            if created_locally:
                shutil.rmtree(cleanup_path, ignore_errors=True)

    def _prepare_source(self, context: dict[str, Any]) -> tuple[Path, Path]:
        workspace = Path(tempfile.mkdtemp(prefix=f"job_{context['job_id']}_"))
        source_dir = workspace / "source"
        source_dir.mkdir(parents=True, exist_ok=True)

        source_type = context["source_type"]
        if source_type == "github_url":
            github_url = context.get("github_url")
            if not github_url:
                raise RuntimeError("Missing github_url for GitHub source job.")
            logger.info("Cloning repository", extra={"event": "source_clone_start", "job_id": context["job_id"]})
            subprocess.run(
                ["git", "clone", "--depth", "1", "--single-branch", github_url, str(source_dir)],
                check=True,
                capture_output=True,
                text=True,
                timeout=180,
            )
            logger.info("Repository cloned", extra={"event": "source_clone_complete", "job_id": context["job_id"]})
            return source_dir, workspace

        storage_key = context.get("storage_key")
        if not storage_key:
            raise RuntimeError("Missing storage_key for uploaded source job.")

        archive_path = workspace / "archive.zip"
        key = storage_key.removeprefix("s3://")
        logger.info("Downloading source archive", extra={"event": "source_download_start", "job_id": context["job_id"]})
        self.s3.download_file(self.bucket_name, key, str(archive_path))

        try:
            with ZipFile(archive_path, "r") as archive:
                archive.extractall(source_dir)
            logger.info("Source archive unpacked", extra={"event": "source_unpack_complete", "job_id": context["job_id"]})
        except Exception as exc:
            raise RuntimeError(f"Failed to unpack source archive: {exc}") from exc

        return source_dir, workspace

    def _replace_findings(
        self,
        conn: psycopg.Connection,
        job_id: str,
        phase: str,
        findings: list[dict[str, Any]],
    ) -> None:
        resolved_phase = self._resolve_analysis_phase(conn, phase)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM analysis_runs WHERE job_id = %s AND phase = %s::analysis_phase_enum",
                (job_id, resolved_phase),
            )
            row = cur.fetchone()
            if row:
                cur.execute("DELETE FROM findings WHERE analysis_run_id = %s", (row[0],))
                cur.execute("DELETE FROM analysis_runs WHERE id = %s", (row[0],))

            run_id = str(uuid.uuid4())
            cur.execute(
                """
                INSERT INTO analysis_runs (id, job_id, phase, summary_json, started_at, finished_at)
                VALUES (%s, %s, %s::analysis_phase_enum, %s::jsonb, NOW(), NOW())
                """,
                (run_id, job_id, resolved_phase, json.dumps({"count": len(findings)})),
            )

            for finding in findings:
                cur.execute(
                    """
                    INSERT INTO findings (
                        analysis_run_id, tool, rule_id, severity, category,
                        file_path, line, message, suggestion, fingerprint
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        run_id,
                        finding["tool"],
                        finding["rule_id"],
                        finding["severity"],
                        finding["category"],
                        finding["file"],
                        finding["line"],
                        finding["message"],
                        finding["suggestion"],
                        finding["fingerprint"],
                    ),
                )

    def _resolve_analysis_phase(self, conn: psycopg.Connection, phase: str) -> str:
        requested = phase.strip()
        requested_lower = requested.lower()

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT e.enumlabel
                FROM pg_type t
                JOIN pg_enum e ON e.enumtypid = t.oid
                WHERE t.typname = 'analysis_phase_enum'
                ORDER BY e.enumsortorder
                """
            )
            labels = [str(row[0]) for row in cur.fetchall()]

        label_map = {label.lower(): label for label in labels}
        if requested_lower in label_map:
            return label_map[requested_lower]
        if requested in labels:
            return requested

        allowed = ", ".join(labels) if labels else "before, after"
        raise RuntimeError(f"Unsupported analysis phase '{phase}'. Allowed values: {allowed}")

    def _update_job_state(self, conn: psycopg.Connection, job_id: str, status: str, progress: int, current_step: str) -> None:
        logger.info("Updating job state", extra={"event": "job_state_update", "job_id": job_id, "status": status})
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE jobs
                SET
                    status = %s::job_status_enum,
                    progress = %s,
                    current_step = %s,
                    started_at = CASE WHEN started_at IS NULL THEN NOW() ELSE started_at END,
                    finished_at = CASE WHEN %s IN ('DONE', 'FAILED') THEN NOW() ELSE finished_at END,
                    error_code = NULL,
                    error_message = NULL
                WHERE id = %s
                """,
                (status, progress, current_step, status, job_id),
            )
            # Commit each state transition so external pollers can observe progress in real time.
            conn.commit()

    def _mark_failed(self, conn: psycopg.Connection, job_id: str, step: str, message: str) -> None:
        logger.error("Marking job failed", extra={"event": "job_mark_failed", "job_id": job_id, "status": "FAILED"})
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE jobs
                SET
                    status = 'FAILED'::job_status_enum,
                    progress = 100,
                    current_step = %s,
                    error_code = 'PIPELINE_ERROR',
                    error_message = %s,
                    started_at = COALESCE(started_at, NOW()),
                    finished_at = NOW()
                WHERE id = %s
                """,
                (step, message[:4000], job_id),
            )

    def _normalize_findings(self, raw_results: dict[str, Any]) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []

        for issue in raw_results.get("bandit", {}).get("results", []):
            file_path = str(issue.get("filename", ""))
            line = int(issue.get("line_number", 0) or 0)
            rule = str(issue.get("test_id", "BANDIT"))
            findings.append(
                {
                    "tool": "bandit",
                    "rule_id": rule,
                    "severity": self._normalize_severity(str(issue.get("issue_severity", "medium"))),
                    "category": "security",
                    "file": file_path,
                    "line": line,
                    "message": str(issue.get("issue_text", "Security issue detected.")),
                    "suggestion": "Review and remediate the reported security issue.",
                    "fingerprint": f"bandit:{rule}:{file_path}:{line}",
                }
            )

        for issue in raw_results.get("pylint", []):
            file_path = str(issue.get("path", ""))
            line = int(issue.get("line", 0) or 0)
            rule = str(issue.get("message-id", "PYLINT"))
            findings.append(
                {
                    "tool": "pylint",
                    "rule_id": rule,
                    "severity": "low",
                    "category": "code_smell",
                    "file": file_path,
                    "line": line,
                    "message": str(issue.get("message", "Pylint issue detected.")),
                    "suggestion": "Apply lint recommendation for cleaner code.",
                    "fingerprint": f"pylint:{rule}:{file_path}:{line}",
                }
            )

        radon_payload = raw_results.get("radon", {})
        if isinstance(radon_payload, dict):
            for file_path, blocks in radon_payload.items():
                if not isinstance(blocks, list):
                    continue
                for block in blocks:
                    complexity = int(block.get("complexity", 0) or 0)
                    line = int(block.get("lineno", 0) or 0)
                    findings.append(
                        {
                            "tool": "radon",
                            "rule_id": "CC",
                            "severity": self._severity_from_complexity(complexity),
                            "category": "complexity",
                            "file": str(file_path),
                            "line": line,
                            "message": f"Cyclomatic complexity is {complexity} for {block.get('name', 'block')}.",
                            "suggestion": "Split logic into smaller functions.",
                            "fingerprint": f"radon:CC:{file_path}:{line}",
                        }
                    )

        for issue in raw_results.get("trufflehog", []):
            source_metadata = issue.get("SourceMetadata", {})
            source_data = source_metadata.get("Data", {}) if isinstance(source_metadata, dict) else {}
            fs_data = source_data.get("Filesystem", {}) if isinstance(source_data, dict) else {}
            file_path = str(fs_data.get("file", ""))
            line = int(fs_data.get("line", 0) or 0)
            rule = str(issue.get("DetectorName", "TRUFFLEHOG"))
            findings.append(
                {
                    "tool": "trufflehog",
                    "rule_id": rule,
                    "severity": "critical",
                    "category": "secrets",
                    "file": file_path,
                    "line": line,
                    "message": "Potential secret detected by TruffleHog.",
                    "suggestion": "Rotate and remove exposed secret material.",
                    "fingerprint": f"trufflehog:{rule}:{file_path}:{line}",
                }
            )

        return findings

    @staticmethod
    def _normalize_severity(value: str) -> str:
        normalized = value.strip().lower()
        if normalized in {"low", "medium", "high", "critical"}:
            return normalized
        return "medium"

    @staticmethod
    def _severity_from_complexity(complexity: int) -> str:
        if complexity >= 20:
            return "high"
        if complexity >= 10:
            return "medium"
        return "low"

    @staticmethod
    def _parse_max_repair_cycles(value: Any) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return 3
        return parsed if parsed > 0 else 3

    def _bounded_repair_cycles(self, requested_cycles: Any) -> int:
        if requested_cycles is None:
            return 1

        parsed = self._parse_max_repair_cycles(requested_cycles)
        return min(parsed, self.max_repair_cycles)


if __name__ == "__main__":  # pragma: no cover
    worker = SqsWorker()
    worker.run_forever()
