import json
from pathlib import Path

import pytest

import main as worker_main


class FakeSqs:
    def __init__(self, messages=None):
        self.messages = messages or []
        self.deleted = []

    def receive_message(self, **kwargs):
        if not self.messages:
            return {}
        message = self.messages.pop(0)
        return {"Messages": [message]}

    def delete_message(self, QueueUrl, ReceiptHandle):
        self.deleted.append((QueueUrl, ReceiptHandle))


class FakeS3:
    def __init__(self):
        self.calls = []

    def download_file(self, bucket, key, destination):
        self.calls.append((bucket, key, destination))


class FakeCursor:
    def __init__(self, rows=None):
        self.rows = list(rows or [])
        self.queries = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query, params=None):
        self.queries.append((query, params))

    def fetchone(self):
        if self.rows:
            return self.rows.pop(0)
        return None

    def fetchall(self):
        if self.rows:
            rows = list(self.rows)
            self.rows.clear()
            return rows
        return []


class FakeConn:
    def __init__(self, rows=None):
        self.autocommit = True
        self.cursor_obj = FakeCursor(rows=rows)
        self.committed = False
        self.rolled_back = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("SQS_QUEUE_URL", "https://example.com/queue")
    monkeypatch.setenv("S3_BUCKET_NAME", "artifacts-bucket")
    monkeypatch.setenv("DB_HOST", "db.example")
    monkeypatch.setenv("DB_NAME", "codequality")
    monkeypatch.setenv("DB_USER", "postgres_admin")
    monkeypatch.setenv("DB_PASSWORD", "secret")
    monkeypatch.setenv("DB_PORT", "5432")


def _new_worker(monkeypatch):
    fake_sqs = FakeSqs()
    fake_s3 = FakeS3()

    def fake_client(service, region_name=None):
        if service == "sqs":
            return fake_sqs
        if service == "s3":
            return fake_s3
        raise AssertionError(service)

    monkeypatch.setattr(worker_main.boto3, "client", fake_client)
    return worker_main.SqsWorker(), fake_sqs, fake_s3


def test_build_database_url_prefers_explicit(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pw@host:5432/db")
    assert worker_main._build_database_url() == "postgresql://user:pw@host:5432/db"


def test_build_database_url_with_password(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DB_HOST", "host")
    monkeypatch.setenv("DB_NAME", "db")
    monkeypatch.setenv("DB_USER", "user")
    monkeypatch.setenv("DB_PASSWORD", "pw")
    monkeypatch.setenv("DB_PORT", "5439")
    assert worker_main._build_database_url() == "postgresql://user:pw@host:5439/db"


def test_build_database_url_without_password(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DB_HOST", "host")
    monkeypatch.setenv("DB_NAME", "db")
    monkeypatch.setenv("DB_USER", "user")
    monkeypatch.delenv("DB_PASSWORD", raising=False)
    monkeypatch.setenv("DB_PORT", "5432")
    assert worker_main._build_database_url() == "postgresql://user@host:5432/db"


def test_build_database_url_raises_without_host(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DB_HOST", raising=False)
    with pytest.raises(RuntimeError, match="DB_HOST or DATABASE_URL"):
        worker_main._build_database_url()


def test_worker_init_requires_queue_and_bucket(monkeypatch, env):
    monkeypatch.setattr(worker_main.boto3, "client", lambda service, region_name=None: object())
    monkeypatch.delenv("SQS_QUEUE_URL", raising=False)
    with pytest.raises(RuntimeError, match="SQS_QUEUE_URL"):
        worker_main.SqsWorker()

    monkeypatch.setenv("SQS_QUEUE_URL", "https://example.com/queue")
    monkeypatch.delenv("S3_BUCKET_NAME", raising=False)
    with pytest.raises(RuntimeError, match="S3_BUCKET_NAME"):
        worker_main.SqsWorker()


def test_receive_and_delete_message(monkeypatch, env):
    worker, fake_sqs, _ = _new_worker(monkeypatch)
    fake_sqs.messages = [{"ReceiptHandle": "rh-1", "Body": "{}"}]

    message = worker._receive_message()
    assert message["ReceiptHandle"] == "rh-1"

    worker._delete_message("rh-1")
    assert fake_sqs.deleted == [(worker.queue_url, "rh-1")]


def test_receive_message_empty_queue(monkeypatch, env):
    worker, _, _ = _new_worker(monkeypatch)
    assert worker._receive_message() is None


def test_process_payload_routes_analyze(monkeypatch, env):
    worker, _, _ = _new_worker(monkeypatch)
    conn = FakeConn()
    observed = {}

    monkeypatch.setattr(worker_main.psycopg, "connect", lambda _: conn)
    monkeypatch.setattr(worker, "_get_job_context", lambda _conn, job_id: {"job_id": job_id, "auto_repair": True})
    monkeypatch.setattr(worker, "_run_repair_pipeline", lambda *_: observed.setdefault("repair", True))
    monkeypatch.setattr(worker, "_run_analysis_pipeline", lambda *_: observed.setdefault("analyze", True))

    worker._process_payload({"job_id": "job_1", "action": "analyze"})
    assert observed["analyze"] is True
    assert conn.autocommit is False
    assert conn.committed is True


def test_process_payload_routes_repair(monkeypatch, env):
    worker, _, _ = _new_worker(monkeypatch)
    conn = FakeConn()
    observed = {}

    monkeypatch.setattr(worker_main.psycopg, "connect", lambda _: conn)
    monkeypatch.setattr(worker, "_get_job_context", lambda _conn, job_id: {"job_id": job_id, "auto_repair": True})
    monkeypatch.setattr(worker, "_run_repair_pipeline", lambda *_, **__: observed.setdefault("repair", True))
    monkeypatch.setattr(worker, "_run_analysis_pipeline", lambda *_: observed.setdefault("analyze", True))

    worker._process_payload({"job_id": "job_2", "action": "repair"})
    assert observed["repair"] is True
    assert "analyze" not in observed


def test_process_payload_requires_job_id(monkeypatch, env):
    worker, _, _ = _new_worker(monkeypatch)
    with pytest.raises(RuntimeError, match="missing job_id"):
        worker._process_payload({})


def test_get_job_context_success(monkeypatch, env):
    worker, _, _ = _new_worker(monkeypatch)
    conn = FakeConn(
        rows=[
            (
                "job_1",
                "QUEUED",
                True,
                "repo_1",
                "upload",
                None,
                "uploads/repo_1/archive.zip",
            )
        ]
    )

    context = worker._get_job_context(conn, "job_1")
    assert context["job_id"] == "job_1"
    assert context["repository_id"] == "repo_1"
    assert context["source_type"] == "upload"


def test_get_job_context_not_found(monkeypatch, env):
    worker, _, _ = _new_worker(monkeypatch)
    conn = FakeConn()
    with pytest.raises(RuntimeError, match="not found"):
        worker._get_job_context(conn, "missing")


def test_run_analysis_pipeline_no_auto_repair(monkeypatch, env, tmp_path):
    worker, _, _ = _new_worker(monkeypatch)
    conn = FakeConn()
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    cleanup = tmp_path / "cleanup"
    cleanup.mkdir()

    states = []
    monkeypatch.setattr(worker, "_prepare_source", lambda context: (source_dir, cleanup))
    monkeypatch.setattr(worker, "_update_job_state", lambda _c, _j, s, _p, _st: states.append(s))
    monkeypatch.setattr(worker, "_replace_findings", lambda *_: None)
    monkeypatch.setattr(worker, "_normalize_findings", lambda _raw, _source_dir: [{"tool": "bandit", "rule_id": "X", "severity": "low", "category": "security", "file": "f.py", "line": 1, "message": "m", "suggestion": "s", "fingerprint": "fp"}])
    monkeypatch.setattr(worker_main.Analyzer, "run_all", lambda self: {})
    monkeypatch.setattr(worker, "_run_repair_pipeline", lambda *_: (_ for _ in ()).throw(AssertionError("unexpected repair")))

    worker._run_analysis_pipeline(
        conn,
        {"job_id": "job_1", "auto_repair": False, "source_type": "upload", "storage_key": "uploads/a.zip"},
        {"job_id": "job_1", "auto_repair": False},
    )

    assert states == ["FETCHING", "ANALYZING", "READY_FOR_REPAIR"]
    assert not cleanup.exists()


def test_run_analysis_pipeline_with_auto_repair(monkeypatch, env, tmp_path):
    worker, _, _ = _new_worker(monkeypatch)
    conn = FakeConn()
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    cleanup = tmp_path / "cleanup"
    cleanup.mkdir()
    called = {}

    monkeypatch.setattr(worker, "_prepare_source", lambda context: (source_dir, cleanup))
    monkeypatch.setattr(worker, "_update_job_state", lambda *_: None)
    monkeypatch.setattr(worker, "_replace_findings", lambda *_: None)
    monkeypatch.setattr(worker, "_normalize_findings", lambda _raw, _source_dir: [])
    monkeypatch.setattr(worker_main.Analyzer, "run_all", lambda self: {})
    monkeypatch.setattr(
        worker,
        "_run_repair_pipeline",
        lambda _conn, _ctx, source_dir=None, requested_cycles=None: called.setdefault(
            "args", (source_dir, requested_cycles)
        ),
    )

    worker._run_analysis_pipeline(
        conn,
        {"job_id": "job_2", "auto_repair": True, "source_type": "upload", "storage_key": "uploads/a.zip"},
        {"job_id": "job_2", "auto_repair": True},
    )

    assert called["args"][0] == source_dir
    assert called["args"][1] is None


def test_run_analysis_pipeline_failure_marks_failed(monkeypatch, env, tmp_path):
    worker, _, _ = _new_worker(monkeypatch)
    conn = FakeConn()
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    cleanup = tmp_path / "cleanup"
    cleanup.mkdir()
    markers = {}

    monkeypatch.setattr(worker, "_prepare_source", lambda context: (source_dir, cleanup))
    monkeypatch.setattr(worker, "_update_job_state", lambda *_: None)
    monkeypatch.setattr(worker_main.Analyzer, "run_all", lambda self: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(worker, "_mark_failed", lambda _c, _j, step, msg: markers.setdefault("v", (step, msg)))

    with pytest.raises(RuntimeError, match="boom"):
        worker._run_analysis_pipeline(
            conn,
            {"job_id": "job_3", "auto_repair": False, "source_type": "upload", "storage_key": "uploads/a.zip"},
            {"job_id": "job_3", "auto_repair": False},
        )

    assert markers["v"][0] == "analysis_failed"
    assert conn.rolled_back is True
    assert conn.committed is True
    assert not cleanup.exists()


def test_run_repair_pipeline_with_existing_source(monkeypatch, env, tmp_path):
    worker, _, _ = _new_worker(monkeypatch)
    conn = FakeConn()
    source_dir = tmp_path / "source"
    source_dir.mkdir(parents=True)
    states = []

    monkeypatch.setattr(worker, "_update_job_state", lambda _c, _j, s, _p, _st: states.append(s))
    monkeypatch.setattr(worker_main.Analyzer, "run_all", lambda self: {})
    monkeypatch.setattr(worker, "_fetch_phase_findings", lambda _c, _j, _phase: [{"file_path": "f.py", "line": 1, "rule_id": "X", "message": "m"}])
    monkeypatch.setattr(worker, "_normalize_findings", lambda _raw, _source_dir: [])
    monkeypatch.setattr(worker, "_replace_findings", lambda *_: None)

    (source_dir / "f.py").write_text("print('x')\n", encoding="utf-8")

    worker._run_repair_pipeline(conn, {"job_id": "job_4"}, source_dir=source_dir)
    assert states == ["REPAIRING", "REANALYZING", "DONE"]


def test_run_repair_pipeline_without_source_creates_and_cleans(monkeypatch, env, tmp_path):
    worker, _, _ = _new_worker(monkeypatch)
    conn = FakeConn()
    source_dir = tmp_path / "source"
    source_dir.mkdir(parents=True)
    cleanup = tmp_path / "cleanup"
    cleanup.mkdir()

    monkeypatch.setattr(worker, "_prepare_source", lambda context: (source_dir, cleanup))
    monkeypatch.setattr(worker, "_update_job_state", lambda *_: None)
    monkeypatch.setattr(worker_main.Analyzer, "run_all", lambda self: {})
    monkeypatch.setattr(worker, "_fetch_phase_findings", lambda _c, _j, _phase: [{"file_path": "f.py", "line": 1, "rule_id": "X", "message": "m"}])
    monkeypatch.setattr(worker, "_normalize_findings", lambda _raw, _source_dir: [])
    monkeypatch.setattr(worker, "_replace_findings", lambda *_: None)

    (source_dir / "f.py").write_text("print('x')\n", encoding="utf-8")

    worker._run_repair_pipeline(conn, {"job_id": "job_5"})
    assert not cleanup.exists()


def test_run_repair_pipeline_failure_marks_failed(monkeypatch, env, tmp_path):
    worker, _, _ = _new_worker(monkeypatch)
    conn = FakeConn()
    source_dir = tmp_path / "source"
    source_dir.mkdir(parents=True)
    cleanup = tmp_path / "cleanup"
    cleanup.mkdir()
    markers = {}

    monkeypatch.setattr(worker, "_prepare_source", lambda context: (source_dir, cleanup))
    monkeypatch.setattr(worker, "_update_job_state", lambda *_: None)
    monkeypatch.setattr(worker, "_fetch_phase_findings", lambda _c, _j, _phase: [{"file_path": "f.py", "line": 1, "rule_id": "X", "message": "m"}])
    monkeypatch.setattr(worker_main.Analyzer, "run_all", lambda self: (_ for _ in ()).throw(RuntimeError("repair boom")))
    monkeypatch.setattr(worker, "_mark_failed", lambda _c, _j, step, msg: markers.setdefault("v", (step, msg)))

    (source_dir / "f.py").write_text("print('x')\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="repair boom"):
        worker._run_repair_pipeline(conn, {"job_id": "job_6"})
    assert markers["v"][0] == "repair_failed"
    assert conn.rolled_back is True
    assert conn.committed is True
    assert not cleanup.exists()


def test_run_repair_pipeline_respects_max_cycle_cap(monkeypatch, env, tmp_path):
    worker, _, _ = _new_worker(monkeypatch)
    worker.max_repair_cycles = 2
    conn = FakeConn()
    source_dir = tmp_path / "source"
    source_dir.mkdir(parents=True)

    steps = []
    monkeypatch.setattr(worker, "_update_job_state", lambda _c, _j, _s, _p, step: steps.append(step))
    monkeypatch.setattr(worker, "_fetch_phase_findings", lambda _c, _j, _phase: [{"file_path": "x.py", "line": 1, "rule_id": "B1", "message": "m"}])
    monkeypatch.setattr(worker_main.Analyzer, "run_all", lambda self: {"bandit": {"results": [{"filename": "x.py", "line_number": 1}]}})
    monkeypatch.setattr(
        worker,
        "_normalize_findings",
        lambda _raw, _source_dir: [
            {
                "tool": "bandit",
                "rule_id": "B1",
                "severity": "low",
                "category": "security",
                "file": "x.py",
                "line": 1,
                "message": "m",
                "suggestion": "s",
                "fingerprint": "fp",
            }
        ],
    )
    monkeypatch.setattr(worker, "_replace_findings", lambda *_: None)

    (source_dir / "x.py").write_text("print('x')\n", encoding="utf-8")

    worker._run_repair_pipeline(
        conn,
        {"job_id": "job_cap"},
        source_dir=source_dir,
        requested_cycles=10,
    )

    cycle_steps = [s for s in steps if "cycle_" in s]
    assert any("cycle_1_of_2" in s for s in cycle_steps)
    assert any("cycle_2_of_2" in s for s in cycle_steps)
    assert not any("cycle_3_of_" in s for s in cycle_steps)


def test_cycle_parsing_and_bounds(monkeypatch, env):
    worker, _, _ = _new_worker(monkeypatch)
    worker.max_repair_cycles = 3

    assert worker._parse_max_repair_cycles("4") == 4
    assert worker._parse_max_repair_cycles("bad") == 3
    assert worker._parse_max_repair_cycles(0) == 3
    assert worker._bounded_repair_cycles(None) == 1
    assert worker._bounded_repair_cycles("2") == 2
    assert worker._bounded_repair_cycles("999") == 3


def test_prepare_source_github_success(monkeypatch, env, tmp_path):
    worker, _, _ = _new_worker(monkeypatch)
    workspace = tmp_path / "ws"
    workspace.mkdir()
    monkeypatch.setattr(worker_main.tempfile, "mkdtemp", lambda prefix=None: str(workspace))

    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return None

    monkeypatch.setattr(worker_main.subprocess, "run", fake_run)

    source, cleanup = worker._prepare_source(
        {"job_id": "job_7", "source_type": "github_url", "github_url": "https://github.com/acme/repo"}
    )

    assert source == workspace / "source"
    assert cleanup == workspace
    assert calls[0][0:2] == ["git", "clone"]


def test_prepare_source_github_missing_url(monkeypatch, env, tmp_path):
    worker, _, _ = _new_worker(monkeypatch)
    workspace = tmp_path / "ws2"
    workspace.mkdir()
    monkeypatch.setattr(worker_main.tempfile, "mkdtemp", lambda prefix=None: str(workspace))

    with pytest.raises(RuntimeError, match="Missing github_url"):
        worker._prepare_source({"job_id": "job_8", "source_type": "github_url"})


def test_prepare_source_upload_success(monkeypatch, env, tmp_path):
    worker, _, fake_s3 = _new_worker(monkeypatch)
    workspace = tmp_path / "ws3"
    workspace.mkdir()
    monkeypatch.setattr(worker_main.tempfile, "mkdtemp", lambda prefix=None: str(workspace))

    def fake_download(bucket, key, destination):
        with worker_main.ZipFile(destination, "w") as zipf:
            zipf.writestr("pkg/app.py", "print('ok')\n")

    fake_s3.download_file = fake_download

    source, cleanup = worker._prepare_source(
        {"job_id": "job_9", "source_type": "upload", "storage_key": "s3://uploads/repo.zip"}
    )

    assert (source / "pkg" / "app.py").exists()
    assert cleanup == workspace


def test_prepare_source_upload_missing_storage_key(monkeypatch, env, tmp_path):
    worker, _, _ = _new_worker(monkeypatch)
    workspace = tmp_path / "ws4"
    workspace.mkdir()
    monkeypatch.setattr(worker_main.tempfile, "mkdtemp", lambda prefix=None: str(workspace))

    with pytest.raises(RuntimeError, match="Missing storage_key"):
        worker._prepare_source({"job_id": "job_10", "source_type": "upload"})


def test_prepare_source_upload_invalid_archive(monkeypatch, env, tmp_path):
    worker, _, fake_s3 = _new_worker(monkeypatch)
    workspace = tmp_path / "ws5"
    workspace.mkdir()
    monkeypatch.setattr(worker_main.tempfile, "mkdtemp", lambda prefix=None: str(workspace))

    def fake_download(bucket, key, destination):
        Path(destination).write_text("not a zip", encoding="utf-8")

    fake_s3.download_file = fake_download

    with pytest.raises(RuntimeError, match="Failed to unpack source archive"):
        worker._prepare_source({"job_id": "job_11", "source_type": "upload", "storage_key": "uploads/repo.zip"})


def test_replace_findings_with_existing_run(monkeypatch, env):
    worker, _, _ = _new_worker(monkeypatch)
    conn = FakeConn(rows=[("run-1",)])
    monkeypatch.setattr(worker_main.uuid, "uuid4", lambda: "uuid-fixed")
    monkeypatch.setattr(worker, "_resolve_analysis_phase", lambda _conn, phase: phase)
    worker._replace_findings(
        conn,
        "job_12",
        "before",
        [
            {
                "tool": "bandit",
                "rule_id": "B1",
                "severity": "high",
                "category": "security",
                "file": "app.py",
                "line": 1,
                "message": "m",
                "suggestion": "s",
                "fingerprint": "fp",
            }
        ],
    )

    sql = "\n".join(query for query, _ in conn.cursor_obj.queries)
    assert "DELETE FROM findings" in sql
    assert "INSERT INTO analysis_runs" in sql
    assert "INSERT INTO findings" in sql


def test_replace_findings_without_existing_run(monkeypatch, env):
    worker, _, _ = _new_worker(monkeypatch)
    conn = FakeConn(rows=[None])
    monkeypatch.setattr(worker, "_resolve_analysis_phase", lambda _conn, phase: phase)
    worker._replace_findings(conn, "job_13", "after", [])
    sql = "\n".join(query for query, _ in conn.cursor_obj.queries)
    assert "DELETE FROM findings" not in sql
    assert "INSERT INTO analysis_runs" in sql


def test_resolve_analysis_phase_case_insensitive(monkeypatch, env):
    worker, _, _ = _new_worker(monkeypatch)
    conn = FakeConn(rows=[("BEFORE",), ("AFTER",)])

    resolved = worker._resolve_analysis_phase(conn, "before")
    assert resolved == "BEFORE"


def test_resolve_analysis_phase_rejects_unknown(monkeypatch, env):
    worker, _, _ = _new_worker(monkeypatch)
    conn = FakeConn(rows=[("BEFORE",), ("AFTER",)])

    with pytest.raises(RuntimeError, match="Unsupported analysis phase"):
        worker._resolve_analysis_phase(conn, "during")


def test_update_job_state_executes_sql(monkeypatch, env):
    worker, _, _ = _new_worker(monkeypatch)
    conn = FakeConn()
    worker._update_job_state(conn, "job_14", "ANALYZING", 50, "running")
    assert "UPDATE jobs" in conn.cursor_obj.queries[0][0]
    assert conn.committed is True


def test_mark_failed_executes_sql_and_truncates(monkeypatch, env):
    worker, _, _ = _new_worker(monkeypatch)
    conn = FakeConn()
    long_message = "x" * 5000
    worker._mark_failed(conn, "job_15", "failed_step", long_message)
    _, params = conn.cursor_obj.queries[0]
    assert params[1] == "x" * 4000


def test_normalize_findings_and_severity_helpers(monkeypatch, env, tmp_path):
    worker, _, _ = _new_worker(monkeypatch)
    source_dir = tmp_path / "src"
    source_dir.mkdir()
    raw = {
        "bandit": {
            "results": [
                {
                    "filename": "a.py",
                    "line_number": 3,
                    "test_id": "B105",
                    "issue_severity": "HIGH",
                    "issue_text": "hardcoded secret",
                },
                {
                    "filename": "hashes.py",
                    "line_number": 10,
                    "test_id": "B324",
                    "issue_severity": "MEDIUM",
                    "issue_text": "Use of weak SHA1 hash for security. Consider usedforsecurity=False",
                }
            ]
        },
        "pylint": [{"path": "b.py", "line": 5, "message-id": "C0114", "message": "missing doc"}],
        "radon": {
            "c.py": [
                {"complexity": 9, "lineno": 2, "name": "f1"},
                {"complexity": 10, "lineno": 4, "name": "f2"},
                {"complexity": 20, "lineno": 6, "name": "f3"},
            ],
            "ignored.py": "invalid",
        },
        "trufflehog": [
            {
                "DetectorName": "AWS",
                "SourceMetadata": {"Data": {"Filesystem": {"file": "d.py", "line": 7}}},
            }
        ],
    }

    findings = worker._normalize_findings(raw, source_dir)
    assert len(findings) == 7
    sha1_finding = next(f for f in findings if f["rule_id"] == "B324")
    assert "SHA-256" in sha1_finding["suggestion"]
    assert "usedforsecurity=False" in sha1_finding["suggestion"]

    assert "MD5" in worker._suggest_bandit_remediation("B303", "Use of insecure md5 hash")
    assert worker._normalize_severity(" unknown ") == "medium"
    assert worker._severity_from_complexity(9) == "low"
    assert worker._severity_from_complexity(10) == "medium"
    assert worker._severity_from_complexity(20) == "high"


def test_normalize_findings_with_non_dict_radon(monkeypatch, env, tmp_path):
    worker, _, _ = _new_worker(monkeypatch)
    source_dir = tmp_path / "src2"
    source_dir.mkdir()
    raw = {
        "bandit": {"results": []},
        "pylint": [],
        "radon": ["not", "a", "dict"],
        "trufflehog": [
            {
                "DetectorName": "GENERIC",
                "SourceMetadata": "not-a-dict",
            }
        ],
    }

    findings = worker._normalize_findings(raw, source_dir)
    assert len(findings) == 1
    assert findings[0]["tool"] == "trufflehog"


def test_run_forever_processes_and_deletes(monkeypatch, env):
    worker, _, _ = _new_worker(monkeypatch)
    sequence = iter(
        [
            {"ReceiptHandle": "rh-2", "MessageId": "m-2", "Body": json.dumps({"job_id": "job_16"})},
            KeyboardInterrupt(),
        ]
    )
    processed = {}
    deleted = {}

    def fake_receive():
        item = next(sequence)
        if isinstance(item, BaseException):
            raise item
        return item

    monkeypatch.setattr(worker, "_receive_message", fake_receive)
    monkeypatch.setattr(worker, "_process_payload", lambda payload: processed.setdefault("payload", payload))
    monkeypatch.setattr(worker, "_delete_message", lambda receipt: deleted.setdefault("receipt", receipt))

    with pytest.raises(KeyboardInterrupt):
        worker.run_forever()

    assert processed["payload"]["job_id"] == "job_16"
    assert deleted["receipt"] == "rh-2"


def test_run_forever_handles_message_failure(monkeypatch, env):
    worker, _, _ = _new_worker(monkeypatch)
    sequence = iter(
        [
            {"ReceiptHandle": "rh-3", "MessageId": "m-3", "Body": "{}"},
            KeyboardInterrupt(),
        ]
    )
    slept = {}

    def fake_receive():
        item = next(sequence)
        if isinstance(item, BaseException):
            raise item
        return item

    monkeypatch.setattr(worker, "_receive_message", fake_receive)
    monkeypatch.setattr(worker, "_process_payload", lambda _payload: (_ for _ in ()).throw(RuntimeError("fail")))
    monkeypatch.setattr(worker_main.time, "sleep", lambda secs: slept.setdefault("secs", secs))

    with pytest.raises(KeyboardInterrupt):
        worker.run_forever()

    assert slept["secs"] == 1


def test_run_forever_skips_empty_polls(monkeypatch, env):
    worker, _, _ = _new_worker(monkeypatch)
    sequence = iter([None, KeyboardInterrupt()])
    observed = {"processed": 0, "deleted": 0}

    def fake_receive():
        item = next(sequence)
        if isinstance(item, BaseException):
            raise item
        return item

    monkeypatch.setattr(worker, "_receive_message", fake_receive)
    monkeypatch.setattr(worker, "_process_payload", lambda payload: observed.__setitem__("processed", observed["processed"] + 1))
    monkeypatch.setattr(worker, "_delete_message", lambda receipt: observed.__setitem__("deleted", observed["deleted"] + 1))

    with pytest.raises(KeyboardInterrupt):
        worker.run_forever()

    assert observed["processed"] == 0
    assert observed["deleted"] == 0


def test_fetch_phase_findings_filters_empty_file_paths(monkeypatch, env):
    worker, _, _ = _new_worker(monkeypatch)
    conn = FakeConn(rows=[("a.py", 4, "R1", "m1"), ("", 2, "R2", "m2"), ("b.py", None, None, None)])
    monkeypatch.setattr(worker, "_resolve_analysis_phase", lambda _conn, _phase: "before")

    findings = worker._fetch_phase_findings(conn, "job_17", "before")

    assert findings == [
        {"file_path": "a.py", "line": 4, "rule_id": "R1", "message": "m1"},
        {"file_path": "b.py", "line": 0, "rule_id": "UNKNOWN", "message": "Issue detected."},
    ]


def test_findings_to_repair_targets_filters_and_defaults(monkeypatch, env):
    worker, _, _ = _new_worker(monkeypatch)

    targets = worker._findings_to_repair_targets(
        [
            {"file": "", "line": 1, "rule_id": "R", "message": "m"},
            {"file": "app.py", "line": None, "rule_id": None, "message": None},
        ]
    )

    assert targets == [
        {"file_path": "app.py", "line": 0, "rule_id": "UNKNOWN", "message": "Issue detected."}
    ]


def test_build_llm_client_branches(monkeypatch, env):
    worker, _, _ = _new_worker(monkeypatch)

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert worker._build_llm_client() is None

    captured = {}

    class FakeOpenAIClient:
        def __init__(self, *, api_key, base_url):
            captured["api_key"] = api_key
            captured["base_url"] = base_url

    monkeypatch.setenv("OPENAI_API_KEY", "k")
    monkeypatch.setattr(worker_main, "OpenAI", FakeOpenAIClient)
    client = worker._build_llm_client()

    assert isinstance(client, FakeOpenAIClient)
    assert captured["api_key"] == "k"
    assert captured["base_url"] == "https://api.deepseek.com"


def test_apply_repairs_for_findings_branches(monkeypatch, env, tmp_path):
    worker, _, _ = _new_worker(monkeypatch)
    source_dir = tmp_path / "src_apply"
    source_dir.mkdir()
    good_file = source_dir / "good.py"
    bad_file = source_dir / "bad.py"
    good_file.write_text("print('good')\n", encoding="utf-8")
    bad_file.write_text("print('bad')\n", encoding="utf-8")

    class FakeRepairman:
        def __init__(self):
            self.applied = []

        def isolate_snippet(self, full_path, line):
            if full_path.endswith("bad.py"):
                raise RuntimeError("cannot isolate")
            if full_path.endswith("empty.py"):
                return {"snippet": "   ", "start_line": 1, "end_line": 1}
            return {"snippet": "print('x')\n", "start_line": 1, "end_line": 1}

        def apply_fix(self, full_path, start_line, end_line, fixed_snippet):
            self.applied.append((full_path, start_line, end_line, fixed_snippet))

    repairman = FakeRepairman()

    assert worker._apply_repairs_for_findings(source_dir, [], repairman, None, "job_apply") == 0

    empty_file = source_dir / "empty.py"
    empty_file.write_text("print('empty')\n", encoding="utf-8")

    monkeypatch.setattr(
        worker,
        "_generate_fixed_snippet",
        lambda **kwargs: None if kwargs["rule_id"] == "NONE" else "print('fixed')",
    )

    applied_count = worker._apply_repairs_for_findings(
        source_dir=source_dir,
        findings=[
            {"file_path": "", "line": 1, "rule_id": "SKIP", "message": "m"},
            {"file_path": "good.py", "line": 0, "rule_id": "SKIP", "message": "m"},
            {"file_path": "../outside.py", "line": 1, "rule_id": "SKIP", "message": "m"},
            {"file_path": "missing.py", "line": 1, "rule_id": "SKIP", "message": "m"},
            {"file_path": "empty.py", "line": 1, "rule_id": "SKIP", "message": "m"},
            {"file_path": "good.py", "line": 1, "rule_id": "NONE", "message": "m"},
            {"file_path": "good.py", "line": 1, "rule_id": "OK", "message": "m"},
            {"file_path": "bad.py", "line": 1, "rule_id": "OK", "message": "m"},
        ],
        repairman=repairman,
        llm_client=None,
        job_id="job_apply",
    )

    assert applied_count == 1
    assert len(repairman.applied) == 1


def test_generate_fixed_snippet_branches(monkeypatch, env):
    worker, _, _ = _new_worker(monkeypatch)
    assert worker._generate_fixed_snippet(None, "print(1)", 1, "R", "m") is None

    class FailingClient:
        class chat:
            class completions:
                @staticmethod
                def create(**kwargs):
                    raise RuntimeError("llm down")

    assert worker._generate_fixed_snippet(FailingClient(), "print(1)", 1, "R", "m") is None

    class ParseFailClient:
        class chat:
            class completions:
                @staticmethod
                def create(**kwargs):
                    return type("Completion", (), {"choices": []})

    assert worker._generate_fixed_snippet(ParseFailClient(), "print(1)", 1, "R", "m") is None

    class EmptyClient:
        class chat:
            class completions:
                @staticmethod
                def create(**kwargs):
                    message = type("Message", (), {"content": "```python\n\n```"})
                    choice = type("Choice", (), {"message": message})
                    return type("Completion", (), {"choices": [choice]})

    assert worker._generate_fixed_snippet(EmptyClient(), "print(1)", 1, "R", "m") is None

    class SuccessClient:
        class chat:
            class completions:
                @staticmethod
                def create(**kwargs):
                    message = type("Message", (), {"content": "```python\nprint(2)\n```"})
                    choice = type("Choice", (), {"message": message})
                    return type("Completion", (), {"choices": [choice]})

    fixed = worker._generate_fixed_snippet(SuccessClient(), "print(1)", 1, "R", "m")
    assert fixed == "print(2)"


def test_prompt_and_code_fence_helpers(monkeypatch, env):
    worker, _, _ = _new_worker(monkeypatch)

    prompt = worker._build_repair_prompt("print(1)", 10, "B1", "issue")
    assert "Rule: B1" in prompt
    assert "print(1)" in prompt

    assert worker._strip_code_fences("  print(1)  ") == "print(1)"
    assert worker._strip_code_fences("```python\nprint(3)\n```") == "print(3)"
    assert worker._strip_code_fences("```") == ""
    assert worker._strip_code_fences("```python\nprint(4)") == "print(4)"


def test_upload_archive_and_upsert_helpers(monkeypatch, env, tmp_path):
    worker, _, fake_s3 = _new_worker(monkeypatch)
    source_dir = tmp_path / "src_zip"
    workspace = tmp_path / "workspace_zip"
    source_dir.mkdir()
    workspace.mkdir()
    (source_dir / "nested").mkdir()
    (source_dir / "nested" / "x.py").write_text("print('x')\n", encoding="utf-8")

    uploads = {}

    def fake_upload(file_name, bucket, key):
        uploads["file_name"] = file_name
        uploads["bucket"] = bucket
        uploads["key"] = key

    fake_s3.upload_file = fake_upload

    storage_key = worker._upload_fixed_repository_archive(
        context={"job_id": "job_up", "storage_key": "uploads/repo.zip"},
        source_dir=source_dir,
        workspace=workspace,
    )
    assert storage_key == "s3://uploads/repo.zip_fixed.zip"
    assert uploads["bucket"] == "artifacts-bucket"
    assert uploads["key"] == "uploads/repo.zip_fixed.zip"

    conn = FakeConn()
    worker._upsert_artifact_record(conn, "job_up", "repaired_source_archive", storage_key, "application/zip")
    queries = [q for q, _ in conn.cursor_obj.queries]
    assert "DELETE FROM artifacts" in queries[0]
    assert "INSERT INTO artifacts" in queries[1]


def test_run_repair_pipeline_upserts_uploaded_artifact(monkeypatch, env, tmp_path):
    worker, _, _ = _new_worker(monkeypatch)
    conn = FakeConn()
    source_dir = tmp_path / "repair_upsert"
    source_dir.mkdir()

    called = {}
    monkeypatch.setattr(worker, "_fetch_phase_findings", lambda _c, _j, _phase: [])
    monkeypatch.setattr(worker, "_build_llm_client", lambda: None)
    monkeypatch.setattr(worker_main.Analyzer, "run_all", lambda self: {})
    monkeypatch.setattr(worker, "_normalize_findings", lambda _raw, _source_dir: [])
    monkeypatch.setattr(worker, "_replace_findings", lambda *_: None)
    monkeypatch.setattr(worker, "_upload_fixed_repository_archive", lambda **kwargs: "s3://uploads/fixed.zip")
    monkeypatch.setattr(worker, "_upsert_artifact_record", lambda **kwargs: called.setdefault("upsert", kwargs))
    monkeypatch.setattr(worker, "_update_job_state", lambda *_: None)

    worker._run_repair_pipeline(conn, {"job_id": "job_upsert", "storage_key": "uploads/r.zip"}, source_dir=source_dir)
    assert called["upsert"]["artifact_type"] == "repaired_source_archive"


def test_resolve_analysis_phase_exact_match_branch(monkeypatch, env):
    worker, _, _ = _new_worker(monkeypatch)
    conn = FakeConn(rows=[("BEFORE",), ("AFTER",)])

    resolved = worker._resolve_analysis_phase(conn, "AFTER")
    assert resolved == "AFTER"


def test_resolve_analysis_phase_fallback_exact_label_branch(monkeypatch, env):
    worker, _, _ = _new_worker(monkeypatch)
    conn = FakeConn(rows=[("AFTER",)])

    class WeirdPhase(str):
        def strip(self):
            return self

        def lower(self):
            return "__not_present__"

    resolved = worker._resolve_analysis_phase(conn, WeirdPhase("AFTER"))
    assert resolved == "AFTER"
