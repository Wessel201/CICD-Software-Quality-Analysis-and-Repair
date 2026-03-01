from fastapi import FastAPI

from app.api.router import api_router


app = FastAPI(
    title="Code Quality Orchestrator API",
    version="0.1.0",
)

app.include_router(api_router, prefix="/api")


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
