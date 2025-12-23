from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.database import get_db
from app.models import Artifact, Job
from app.schemas.artifact import ArtifactResponse

router = APIRouter()


@router.get("/jobs/{job_id}/artifacts", response_model=List[ArtifactResponse])
async def list_job_artifacts(
    job_id: str,
    db: AsyncSession = Depends(get_db)
) -> List[Artifact]:
    """List all artifacts for a job"""
    job = await db.get(Job, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    result = await db.execute(
        select(Artifact).where(Artifact.job_id == job_id)
    )
    return result.scalars().all()


@router.get("/artifacts/{artifact_id}", response_model=ArtifactResponse)
async def get_artifact(
    artifact_id: str,
    db: AsyncSession = Depends(get_db)
) -> Artifact:
    """Get a specific artifact by ID"""
    artifact = await db.get(Artifact, artifact_id)
    if not artifact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artifact not found"
        )
    return artifact


@router.get("/artifacts/{artifact_id}/download-url")
async def get_artifact_download_url(
    artifact_id: str,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Get a pre-signed download URL for an artifact"""
    artifact = await db.get(Artifact, artifact_id)
    if not artifact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artifact not found"
        )
    
    # TODO: Generate pre-signed S3 URL
    # For now, return a placeholder
    return {
        "download_url": f"https://storage.example.com/download/{artifact.uri}",
        "expires_in": 3600
    }
