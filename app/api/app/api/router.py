from fastapi import APIRouter

from app.api.routes.jobs import router as jobs_router
from app.api.routes.repositories import router as repositories_router


api_router = APIRouter()
api_router.include_router(repositories_router, prefix="/repositories", tags=["repositories"])
api_router.include_router(jobs_router, prefix="/v1/jobs", tags=["jobs"])
