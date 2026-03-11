from pydantic import BaseModel, HttpUrl


class GitRepositoryLinkRequest(BaseModel):
    repo_url: HttpUrl


class RepositorySubmissionResponse(BaseModel):
    submission_id: str
    source_type: str
    detail: str
