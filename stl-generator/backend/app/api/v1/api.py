from fastapi import APIRouter

from app.api.v1.endpoints import projects, jobs, artifacts, uploads

api_router = APIRouter()

api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
api_router.include_router(artifacts.router, prefix="/artifacts", tags=["artifacts"])
api_router.include_router(uploads.router, prefix="/uploads", tags=["uploads"])
