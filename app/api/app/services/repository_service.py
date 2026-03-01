from pathlib import Path
from shutil import rmtree
import subprocess
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from uuid import uuid4
import json

from fastapi import HTTPException, UploadFile


class RepositoryService:
    ALLOWED_ARCHIVE_EXTENSIONS = {".zip", ".tar", ".gz", ".tgz", ".tar.gz"}
    MAX_REPOSITORY_SIZE_BYTES = 100 * 1024 * 1024
    CHUNK_SIZE_BYTES = 1024 * 1024
    GIT_CLONE_TIMEOUT_SECONDS = 120

    def __init__(self, uploads_dir: Path | None = None) -> None:
        self.uploads_dir = uploads_dir or Path("uploads")

    def is_supported_archive(self, filename: str) -> bool:
        lowercase_name = filename.lower()
        return any(lowercase_name.endswith(ext) for ext in self.ALLOWED_ARCHIVE_EXTENSIONS)

    def store_uploaded_archive(self, file: UploadFile) -> tuple[str, str]:
        submission_id = str(uuid4())
        destination_dir = self.uploads_dir / submission_id
        destination_dir.mkdir(parents=True, exist_ok=True)

        destination_file = destination_dir / str(file.filename)
        total_size = 0

        try:
            with destination_file.open("wb") as output_buffer:
                while True:
                    chunk = file.file.read(self.CHUNK_SIZE_BYTES)
                    if not chunk:
                        break
                    total_size += len(chunk)
                    if total_size > self.MAX_REPOSITORY_SIZE_BYTES:
                        raise HTTPException(
                            status_code=400,
                            detail="Repository archive exceeds maximum allowed size of 100 MB.",
                        )
                    output_buffer.write(chunk)
        except HTTPException:
            if destination_file.exists():
                destination_file.unlink()
            if destination_dir.exists() and not any(destination_dir.iterdir()):
                destination_dir.rmdir()
            raise

        return submission_id, destination_file.name

    def clone_public_repository(self, repo_url: str) -> tuple[str, str]:
        self._validate_github_repo_size_limit(repo_url)

        submission_id = str(uuid4())
        destination_dir = self.uploads_dir / submission_id
        source_dir = destination_dir / "source"
        source_dir.parent.mkdir(parents=True, exist_ok=True)

        try:
            commit_hash = self._clone_repository_to_disk(repo_url, source_dir)
        except HTTPException:
            if destination_dir.exists():
                rmtree(destination_dir, ignore_errors=True)
            raise

        return submission_id, commit_hash

    def _extract_github_owner_repo(self, repo_url: str) -> tuple[str, str]:
        parsed = urlparse(repo_url)
        if parsed.netloc.lower() != "github.com":
            raise HTTPException(status_code=400, detail="Only public github.com repositories are supported.")

        path_parts = [segment for segment in parsed.path.split("/") if segment]
        if len(path_parts) < 2:
            raise HTTPException(
                status_code=400,
                detail="Repository URL must include owner and repository name.",
            )

        owner = path_parts[0]
        repo = path_parts[1]
        if repo.endswith(".git"):
            repo = repo[:-4]

        if not owner or not repo:
            raise HTTPException(
                status_code=400,
                detail="Repository URL must include valid owner and repository name.",
            )
        return owner, repo

    def _validate_github_repo_size_limit(self, repo_url: str) -> None:
        owner, repo = self._extract_github_owner_repo(repo_url)
        api_url = f"https://api.github.com/repos/{owner}/{repo}"

        request = Request(
            api_url,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "code-quality-orchestrator",
            },
            method="GET",
        )

        try:
            with urlopen(request, timeout=10) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            if exc.code == 404:
                raise HTTPException(status_code=400, detail="Repository not found or not public.") from exc
            raise HTTPException(status_code=502, detail="Could not validate repository size from GitHub.") from exc
        except URLError as exc:
            raise HTTPException(status_code=502, detail="Could not reach GitHub to validate repository size.") from exc

        repo_size_kb = payload.get("size")
        if repo_size_kb is None:
            raise HTTPException(status_code=502, detail="GitHub did not return repository size.")

        repo_size_bytes = int(repo_size_kb) * 1024
        if repo_size_bytes > self.MAX_REPOSITORY_SIZE_BYTES:
            raise HTTPException(status_code=400, detail="Repository exceeds maximum allowed size of 100 MB.")

    def _directory_size_bytes(self, directory: Path) -> int:
        total_size = 0
        for path in directory.rglob("*"):
            if path.is_file():
                total_size += path.stat().st_size
                if total_size > self.MAX_REPOSITORY_SIZE_BYTES:
                    break
        return total_size

    def _clone_repository_to_disk(self, repo_url: str, target_directory: Path) -> str:
        try:
            subprocess.run(
                [
                    "git",
                    "clone",
                    "--depth",
                    "1",
                    "--single-branch",
                    repo_url,
                    str(target_directory),
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=self.GIT_CLONE_TIMEOUT_SECONDS,
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=500, detail="Git is not installed on the API host.") from exc
        except subprocess.TimeoutExpired as exc:
            raise HTTPException(status_code=504, detail="Repository clone timed out.") from exc
        except subprocess.CalledProcessError as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to clone repository: {exc.stderr.strip() or 'unknown git error'}",
            ) from exc

        repository_size = self._directory_size_bytes(target_directory)
        if repository_size > self.MAX_REPOSITORY_SIZE_BYTES:
            raise HTTPException(status_code=400, detail="Cloned repository exceeds maximum allowed size of 100 MB.")

        try:
            revision_result = subprocess.run(
                ["git", "-C", str(target_directory), "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
                timeout=15,
            )
        except subprocess.CalledProcessError as exc:
            raise HTTPException(status_code=500, detail="Failed to determine cloned repository revision.") from exc
        except subprocess.TimeoutExpired as exc:
            raise HTTPException(status_code=500, detail="Timed out while reading cloned repository revision.") from exc

        return revision_result.stdout.strip()
