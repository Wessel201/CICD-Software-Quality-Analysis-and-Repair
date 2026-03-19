from fastapi import FastAPI
from fastapi import HTTPException, Request
from fastapi import status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import json
import logging
import os
import sys
import secrets
import time
from typing import Any

from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app.api.router import api_router
from app.db.init_db import init_db


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "service": "api",
            "event": getattr(record, "event", "log"),
            "message": record.getMessage(),
        }

        for field in ["job_id", "status", "duration_ms", "method", "path"]:
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


app = FastAPI(
    title="Code Quality Orchestrator API",
    version="0.1.0",
)


def _infer_error_code(status_code: int, message: str) -> str:
    normalized = message.lower()

    if "database" in normalized and ("connect" in normalized or "connection" in normalized):
        return "DB_UNAVAILABLE"
    if "repository source not found" in normalized or "cloned source directory is missing" in normalized:
        return "SOURCE_DIRECTORY_MISSING"
    if "no uploaded archive found" in normalized:
        return "SOURCE_ARCHIVE_MISSING"
    if "source file not found" in normalized:
        return "SOURCE_FILE_NOT_FOUND"
    if "failed to read source file" in normalized:
        return "SOURCE_FILE_READ_FAILED"
    if "outside the job source directory" in normalized:
        return "SOURCE_PATH_FORBIDDEN"
    if "s3_bucket_name is not configured" in normalized:
        return "S3_BUCKET_NOT_CONFIGURED"
    if "failed to generate artifact download url" in normalized:
        return "S3_DOWNLOAD_URL_FAILED"
    if "failed to generate upload url" in normalized:
        return "S3_UPLOAD_URL_FAILED"
    if "failed to upload repository archive to s3" in normalized:
        return "S3_UPLOAD_FAILED"
    if "artifact file is missing from storage" in normalized:
        return "ARTIFACT_STORAGE_MISSING"
    if "artifact not found" in normalized:
        return "ARTIFACT_NOT_FOUND"
    if "repository not found for job" in normalized:
        return "REPOSITORY_NOT_FOUND"
    if "job not found" in normalized:
        return "JOB_NOT_FOUND"
    if "failed to submit job to sqs" in normalized:
        return "SQS_SUBMIT_FAILED"
    if "sqs_queue_url is not configured" in normalized:
        return "SQS_QUEUE_NOT_CONFIGURED"
    if status_code == status.HTTP_401_UNAUTHORIZED:
        return "AUTH_INVALID_API_KEY"
    if status_code == status.HTTP_403_FORBIDDEN:
        return "FORBIDDEN"
    if status_code == status.HTTP_404_NOT_FOUND:
        return "NOT_FOUND"
    if status_code == status.HTTP_409_CONFLICT:
        return "STATE_CONFLICT"
    if 400 <= status_code < 500:
        return "REQUEST_INVALID"
    return "INTERNAL_ERROR"


def _build_error_payload(
    *,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    # Keep legacy `detail` for backwards compatibility with existing frontend handling.
    payload: dict[str, Any] = {
        "detail": message,
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        },
    }
    return payload


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict) and isinstance(exc.detail.get("error"), dict):
        nested = exc.detail["error"]
        message = str(nested.get("message") or "Request failed.")
        code = str(nested.get("code") or _infer_error_code(exc.status_code, message))
        details = nested.get("details") if isinstance(nested.get("details"), dict) else {}
        payload = _build_error_payload(code=code, message=message, details=details)
        return JSONResponse(status_code=exc.status_code, content=payload)

    message = str(exc.detail) if exc.detail else "Request failed."
    code = _infer_error_code(exc.status_code, message)
    payload = _build_error_payload(code=code, message=message, details={"path": str(request.url.path)})
    return JSONResponse(status_code=exc.status_code, content=payload)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    payload = _build_error_payload(
        code="REQUEST_VALIDATION_FAILED",
        message="Request validation failed.",
        details={"errors": exc.errors(), "path": str(request.url.path)},
    )
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=payload)


@app.exception_handler(OperationalError)
async def db_operational_exception_handler(request: Request, exc: OperationalError) -> JSONResponse:
    logger.exception(
        "Database connectivity failure",
        extra={"event": "db_operational_error", "path": request.url.path, "status": status.HTTP_503_SERVICE_UNAVAILABLE},
    )
    payload = _build_error_payload(
        code="DB_UNAVAILABLE",
        message="Database is unavailable.",
        details={"path": str(request.url.path)},
    )
    return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=payload)


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    logger.exception(
        "Database operation failed",
        extra={"event": "db_query_error", "path": request.url.path, "status": status.HTTP_500_INTERNAL_SERVER_ERROR},
    )
    payload = _build_error_payload(
        code="DB_QUERY_FAILED",
        message="Database operation failed.",
        details={"path": str(request.url.path)},
    )
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=payload)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(
        "Unhandled API exception",
        extra={"event": "api_unhandled_exception", "path": request.url.path, "status": status.HTTP_500_INTERNAL_SERVER_ERROR},
    )
    payload = _build_error_payload(
        code="API_INTERNAL_ERROR",
        message="Unexpected server error.",
        details={"path": str(request.url.path)},
    )
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=payload)


def _is_api_key_valid(request: Request) -> bool:
    configured_api_key = os.getenv("API_KEY")
    if not configured_api_key:
        # Keep local development and tests working when API_KEY is not configured.
        return True

    provided_api_key = request.headers.get("x-api-key") or request.query_params.get("api_key", "")
    return secrets.compare_digest(provided_api_key, configured_api_key)


@app.middleware("http")
async def verify_api_key(request: Request, call_next):
    is_api_request = request.url.path.startswith("/api")
    started_at = time.perf_counter()

    if is_api_request and not _is_api_key_valid(request):
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        logger.warning(
            "Request rejected due to invalid or missing API key",
            extra={
                "event": "api_key_rejected",
                "path": request.url.path,
                "method": request.method,
                "status": status.HTTP_401_UNAUTHORIZED,
                "duration_ms": duration_ms,
            },
        )
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content=_build_error_payload(
                code="AUTH_INVALID_API_KEY",
                message="Invalid or missing API key.",
                details={"path": str(request.url.path)},
            ),
        )

    try:
        response = await call_next(request)
    except Exception:
        if is_api_request:
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            logger.exception(
                "API request failed",
                extra={
                    "event": "api_request_failed",
                    "path": request.url.path,
                    "method": request.method,
                    "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                    "duration_ms": duration_ms,
                },
            )
        raise

    if is_api_request:
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        logger.info(
            "API request completed",
            extra={
                "event": "api_request_completed",
                "path": request.url.path,
                "method": request.method,
                "status": response.status_code,
                "duration_ms": duration_ms,
            },
        )

    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

if os.getenv("AUTO_INIT_DB", "false").lower() == "true":
    logger.info("Initializing database on startup", extra={"event": "db_init_start"})
    init_db()
    logger.info("Database initialization complete", extra={"event": "db_init_complete"})

app.include_router(api_router, prefix="/api")
logger.info("API router registered", extra={"event": "router_registered", "path": "/api"})


@app.get("/health")
def health_check() -> dict[str, str]:
    logger.info("Health check requested", extra={"event": "health_check", "path": "/health"})
    return {"status": "ok"}
