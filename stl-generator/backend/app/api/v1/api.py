from fastapi import APIRouter

from app.api.v1.endpoints import projects, jobs, artifacts, uploads, settings

api_router = APIRouter()

api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(jobs.router, tags=["jobs"])
api_router.include_router(artifacts.router, tags=["artifacts"])
api_router.include_router(uploads.router, prefix="/uploads", tags=["uploads"])
api_router.include_router(settings.router, prefix="/system", tags=["settings"])

