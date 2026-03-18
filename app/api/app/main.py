from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import json
import logging
import os
import sys

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
