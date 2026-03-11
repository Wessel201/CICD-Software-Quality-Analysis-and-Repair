from fastapi import APIRouter

from app.api.routes.jobs import router as jobs_router


api_router = APIRouter()
api_router.include_router(jobs_router, prefix="/v1/jobs", tags=["jobs"])
