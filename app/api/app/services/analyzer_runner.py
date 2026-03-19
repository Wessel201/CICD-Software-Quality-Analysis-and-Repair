from pathlib import Path
from shutil import rmtree, unpack_archive
import json
import os
import subprocess

import boto3
from fastapi import HTTPException

from app.schemas.job import Finding


class AnalyzerRunner:
    def __init__(self, uploads_dir: Path | None = None) -> None:
        self.uploads_dir = uploads_dir or Path("uploads")

    def analyze_repository(self, repository_id: str, source_type: str, phase: str) -> list[Finding]:
        findings, _ = self.analyze_repository_with_reports(repository_id=repository_id, source_type=source_type, phase=phase)
        return findings

    def analyze_repository_with_reports(
        self,
        repository_id: str,
        source_type: str,
        phase: str,
        storage_key: str | None = None,
        github_url: str | None = None,
    ) -> tuple[list[Finding], dict[str, object]]:
        source_directory = self._resolve_source_directory(
            repository_id=repository_id,
            source_type=source_type,
            phase=phase,
            storage_key=storage_key,
            github_url=github_url,
        )

        findings: list[Finding] = []
        reports: dict[str, object] = {}

        bandit_findings, bandit_report = self._run_bandit(source_directory)
        if bandit_report is not None:
            reports["bandit"] = bandit_report
        findings.extend(bandit_findings)

        ruff_findings, ruff_report = self._run_ruff(source_directory)
        if ruff_report is not None:
            reports["ruff"] = ruff_report
        findings.extend(ruff_findings)

        radon_findings, radon_report = self._run_radon(source_directory)
        if radon_report is not None:
            reports["radon"] = radon_report
        findings.extend(radon_findings)

        trufflehog_findings, trufflehog_report = self._run_trufflehog(source_directory)
        if trufflehog_report is not None:
            reports["trufflehog"] = trufflehog_report
        findings.extend(trufflehog_findings)

        return findings, reports

    def _resolve_source_directory(
        self,
        repository_id: str,
        source_type: str,
        phase: str,
        storage_key: str | None = None,
        github_url: str | None = None,
    ) -> Path:
        repository_root = self.uploads_dir / repository_id
        repository_root.mkdir(parents=True, exist_ok=True)

        if source_type == "github_url":
            source_directory = repository_root / "source"
            if not source_directory.exists():
                if github_url:
                    try:
                        subprocess.run(
                            ["git", "clone", "--depth", "1", "--single-branch", github_url, str(source_directory)],
                            check=True,
                            capture_output=True,
                            text=True,
                            timeout=180,
                        )
                    except Exception as exc:
                        raise HTTPException(status_code=500, detail=f"Cloned source directory is missing for {repository_id}.") from exc
                else:
                    raise HTTPException(status_code=500, detail=f"Cloned source directory is missing for {repository_id}.")
            return source_directory

        source_directory = repository_root / "source"
        if source_directory.exists():
            return source_directory

        archive_files = [path for path in repository_root.iterdir() if path.is_file()]
        if archive_files:
            archive_file = archive_files[0]
        elif storage_key:
            archive_file = self._download_archive_from_s3(repository_root=repository_root, storage_key=storage_key)
        else:
            raise HTTPException(status_code=500, detail=f"No uploaded archive found for {repository_id}.")

        source_directory.mkdir(parents=True, exist_ok=True)

        try:
            unpack_archive(str(archive_file), str(source_directory))
        except (ValueError, RuntimeError) as exc:
            rmtree(source_directory, ignore_errors=True)
            raise HTTPException(status_code=400, detail=f"Failed to extract uploaded archive {archive_file.name}.") from exc

        return source_directory

    def _download_archive_from_s3(self, repository_root: Path, storage_key: str) -> Path:
        bucket = os.getenv("S3_BUCKET_NAME")
        if not bucket:
            raise HTTPException(status_code=500, detail="S3 bucket is not configured for source retrieval.")

        key = storage_key.removeprefix("s3://")
        suffix = Path(key).suffix or ".zip"
        local_archive = repository_root / f"source_from_s3{suffix}"

        try:
            s3 = boto3.client("s3", region_name=os.getenv("AWS_REGION", "eu-central-1"))
            s3.download_file(bucket, key, str(local_archive))
        except Exception as exc:
            raise HTTPException(status_code=500, detail="Failed to download source archive from S3.") from exc

        return local_archive

    def _run_bandit(self, source_directory: Path) -> tuple[list[Finding], dict[str, object] | None]:
        result = self._execute_command(["bandit", "-r", str(source_directory), "-f", "json"])
        if result is None:
            return [], None

        if result.returncode not in {0, 1}:
            return [], None

        payload = self._load_json_object(result.stdout)
        issues = payload.get("results", []) if isinstance(payload, dict) else []

        findings: list[Finding] = []
        for issue in issues:
            file_path = str(issue.get("filename", ""))
            line_no = int(issue.get("line_number", 0) or 0)
            snippet, snippet_start = self._extract_snippet(file_path, line_no)
            rule_id = str(issue.get("test_id", "BANDIT"))
            message = str(issue.get("issue_text", "Security issue detected."))
            findings.append(
                Finding(
                    tool="bandit",
                    rule_id=rule_id,
                    severity=self._normalize_severity(str(issue.get("issue_severity", "medium"))),
                    category="security",
                    file=file_path,
                    line=line_no,
                    message=message,
                    suggestion=self._suggest_bandit_remediation(rule_id, message),
                    snippet=snippet,
                    snippet_start=snippet_start,
                )
            )
        return findings, payload

    def _run_ruff(self, source_directory: Path) -> tuple[list[Finding], list[dict] | None]:
        result = self._execute_command(["ruff", "check", str(source_directory), "--output-format", "json"])
        if result is None:
            return [], None

        if result.returncode not in {0, 1}:
            return [], None

        payload = self._load_json_array(result.stdout)
        findings: list[Finding] = []

        for issue in payload:
            location = issue.get("location", {}) if isinstance(issue, dict) else {}
            file_path = str(issue.get("filename", ""))
            line_no = int(location.get("row", 0) or 0)
            snippet, snippet_start = self._extract_snippet(file_path, line_no)
            findings.append(
                Finding(
                    tool="ruff",
                    rule_id=str(issue.get("code", "RUFF")),
                    severity="low",
                    category="code_smell",
                    file=file_path,
                    line=line_no,
                    message=str(issue.get("message", "Ruff issue detected.")),
                    suggestion="Apply lint recommendation for cleaner code.",
                    snippet=snippet,
                    snippet_start=snippet_start,
                )
            )
        return findings, payload

    def _run_radon(self, source_directory: Path) -> tuple[list[Finding], dict[str, object] | None]:
        result = self._execute_command(["radon", "cc", str(source_directory), "-j", "-s"])
        if result is None:
            return [], None

        if result.returncode != 0:
            return [], None

        payload = self._load_json_object(result.stdout)
        findings: list[Finding] = []
        if not isinstance(payload, dict):
            return findings, payload

        for file_path, entries in payload.items():
            if not isinstance(entries, list):
                continue
            for entry in entries:
                complexity = int(entry.get("complexity", 0) or 0)
                line_no = int(entry.get("lineno", 0) or 0)
                snippet, snippet_start = self._extract_snippet(file_path, line_no)
                findings.append(
                    Finding(
                        tool="radon",
                        rule_id="CC",
                        severity=self._severity_from_complexity(complexity),
                        category="complexity",
                        file=str(file_path),
                        line=line_no,
                        message=f"Cyclomatic complexity is {complexity} for {entry.get('name', 'block')}.",
                        suggestion="Split logic into smaller functions.",
                        snippet=snippet,
                        snippet_start=snippet_start,
                    )
                )
        return findings, payload

    def _run_trufflehog(self, source_directory: Path) -> tuple[list[Finding], list[dict] | None]:
        result = self._execute_command(["trufflehog", "filesystem", str(source_directory), "--json"])
        if result is None:
            return [], None

        if result.returncode not in {0, 1}:
            return [], None

        findings: list[Finding] = []
        raw_results: list[dict] = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue

            if isinstance(payload, dict):
                raw_results.append(payload)

            source_metadata = payload.get("SourceMetadata", {})
            source_data = source_metadata.get("Data", {}) if isinstance(source_metadata, dict) else {}
            filesystem_info = source_data.get("Filesystem", {}) if isinstance(source_data, dict) else {}

            file_path = str(filesystem_info.get("file", ""))
            line_no = int(filesystem_info.get("line", 0) or 0)
            snippet, snippet_start = self._extract_snippet(file_path, line_no)
            findings.append(
                Finding(
                    tool="trufflehog",
                    rule_id=str(payload.get("DetectorName", "TRUFFLEHOG")),
                    severity="critical",
                    category="secrets",
                    file=file_path,
                    line=line_no,
                    message="Potential secret detected by TruffleHog.",
                    suggestion="Rotate and remove exposed secret material.",
                    snippet=snippet,
                    snippet_start=snippet_start,
                )
            )

        return findings, raw_results

    def read_source_file(
        self,
        repository_id: str,
        source_type: str,
        file_path: str,
        phase: str = "before",
        storage_key: str | None = None,
        github_url: str | None = None,
    ) -> list[str]:
        """Return all lines of a source file, validating the path stays within the job's source directory."""
        source_directory = self._resolve_source_directory(
            repository_id=repository_id,
            source_type=source_type,
            phase=phase,
            storage_key=storage_key,
            github_url=github_url,
        ).resolve()

        requested_path = Path(file_path)
        requested = requested_path.resolve() if requested_path.is_absolute() else (source_directory / requested_path).resolve()

        # Security: prevent path traversal — file must be inside the source directory
        try:
            requested.relative_to(source_directory)
        except ValueError as exc:
            raise HTTPException(status_code=403, detail="File path is outside the job source directory.") from exc

        if not requested.is_file():
            raise HTTPException(status_code=404, detail="Source file not found.")

        try:
            return requested.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as exc:
            raise HTTPException(status_code=500, detail=f"Failed to read source file.") from exc

    def build_source_archive(
        self,
        repository_id: str,
        source_type: str,
        phase: str = "before",
        storage_key: str | None = None,
        github_url: str | None = None,
    ) -> bytes:
        """Zip all Python files in the source directory and return the zip bytes."""
        import zipfile
        import io
        source_dir = self._resolve_source_directory(
            repository_id=repository_id,
            source_type=source_type,
            phase=phase,
            storage_key=storage_key,
            github_url=github_url,
        ).resolve()
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(source_dir.rglob("*.py")):
                if path.is_file():
                    try:
                        zf.write(path, path.relative_to(source_dir))
                    except ValueError:
                        pass
        return buf.getvalue()

    @staticmethod
    def _extract_snippet(file_path: str, line: int, context: int = 3) -> tuple[list[str], int]:
        """Read `context` lines before and after `line` from the file.
        Returns (lines, start_line) where start_line is 1-based.
        Returns ([], 0) if the file cannot be read.
        """
        try:
            path = Path(file_path)
            if not path.is_file():
                return [], 0
            all_lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return [], 0

        total = len(all_lines)
        # Convert 1-based `line` to 0-based index
        idx = max(0, line - 1)
        start_idx = max(0, idx - context)
        end_idx = min(total, idx + context + 1)
        return all_lines[start_idx:end_idx], start_idx + 1  # return 1-based start

    @staticmethod
    def _execute_command(command: list[str]) -> subprocess.CompletedProcess[str] | None:
        try:
            return subprocess.run(command, capture_output=True, text=True, check=False)
        except FileNotFoundError:
            return None

    @staticmethod
    def _load_json_object(content: str) -> dict:
        if not content.strip():
            return {}
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _load_json_array(content: str) -> list[dict]:
        if not content.strip():
            return []
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            return []
        return payload if isinstance(payload, list) else []

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
    def _suggest_bandit_remediation(rule_id: str, issue_text: str) -> str:
        normalized_rule = rule_id.strip().upper()
        issue_lower = issue_text.lower()

        if normalized_rule == "B324" or "sha1" in issue_lower or "weak hash" in issue_lower:
            return (
                "Replace SHA1 with a collision-resistant hash such as SHA-256 (hashlib.sha256). "
                "If the hash is not security-relevant and must remain for compatibility, pass "
                "usedforsecurity=False and document the rationale."
            )

        if "md5" in issue_lower:
            return (
                "Replace MD5 with a stronger hash such as SHA-256 (hashlib.sha256) for security "
                "sensitive use cases."
            )

        return "Review and remediate the reported security issue."
