from pathlib import Path
from shutil import copyfileobj
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from uuid import uuid4
import json

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.schemas.repository import GitRepositoryLinkRequest, RepositorySubmissionResponse


router = APIRouter()

ALLOWED_ARCHIVE_EXTENSIONS = {".zip", ".tar", ".gz", ".tgz", ".tar.gz"}
UPLOADS_DIR = Path("uploads")
MAX_REPOSITORY_SIZE_BYTES = 100 * 1024 * 1024  # 100 MB
CHUNK_SIZE_BYTES = 1024 * 1024  # 1 MB


def _is_supported_archive(filename: str) -> bool:
    lowercase_name = filename.lower()
    return any(lowercase_name.endswith(ext) for ext in ALLOWED_ARCHIVE_EXTENSIONS)


def _extract_github_owner_repo(repo_url: str) -> tuple[str, str]:
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


def _validate_github_repo_size_limit(repo_url: str) -> None:
    owner, repo = _extract_github_owner_repo(repo_url)
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

    # GitHub "size" is in KB
    repo_size_kb = payload.get("size")
    if repo_size_kb is None:
        raise HTTPException(status_code=502, detail="GitHub did not return repository size.")

    repo_size_bytes = int(repo_size_kb) * 1024
    if repo_size_bytes > MAX_REPOSITORY_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="Repository exceeds maximum allowed size of 100 MB.")


@router.post("/upload", response_model=RepositorySubmissionResponse)
def upload_repository(file: UploadFile = File(...)) -> RepositorySubmissionResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="A repository archive file is required.")

    if not _is_supported_archive(file.filename):
        raise HTTPException(
            status_code=400,
            detail="Unsupported archive format. Allowed: .zip, .tar, .gz, .tgz, .tar.gz",
        )

    submission_id = str(uuid4())
    destination_dir = UPLOADS_DIR / submission_id
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination_file = destination_dir / file.filename

    total_size = 0
    try:
        with destination_file.open("wb") as output_buffer:
            while True:
                chunk = file.file.read(CHUNK_SIZE_BYTES)
                if not chunk:
                    break
                total_size += len(chunk)
                if total_size > MAX_REPOSITORY_SIZE_BYTES:
                    raise HTTPException(
                        status_code=400,
                        detail="Repository archive exceeds maximum allowed size of 100 MB.",
                    )
                output_buffer.write(chunk)
    except HTTPException:
        if destination_file.exists():
            destination_file.unlink()
        raise

    return RepositorySubmissionResponse(
        submission_id=submission_id,
        source_type="upload",
        detail=f"Repository archive stored as {destination_file.name}",
    )


@router.post("/link", response_model=RepositorySubmissionResponse)
def submit_repository_link(payload: GitRepositoryLinkRequest) -> RepositorySubmissionResponse:
    parsed_url = urlparse(str(payload.repo_url))

    if parsed_url.username or parsed_url.password:
        raise HTTPException(status_code=400, detail="Repository URL must not include credentials.")

    _validate_github_repo_size_limit(str(payload.repo_url))

    submission_id = str(uuid4())
    return RepositorySubmissionResponse(
        submission_id=submission_id,
        source_type="git_link",
        detail="Public repository URL accepted.",
    )
