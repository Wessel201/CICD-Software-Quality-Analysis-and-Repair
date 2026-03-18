from fastapi import FastAPI
from fastapi import Request
from fastapi import status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import json
import logging
import os
import sys
import secrets
import time

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
            content={"detail": "Invalid or missing API key."},
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
