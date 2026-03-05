from fastapi import FastAPI
import os

from app.api.router import api_router
from app.db.init_db import init_db


app = FastAPI(
    title="Code Quality Orchestrator API",
    version="0.1.0",
)

if os.getenv("AUTO_INIT_DB", "false").lower() == "true":
    init_db()

app.include_router(api_router, prefix="/api")


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
