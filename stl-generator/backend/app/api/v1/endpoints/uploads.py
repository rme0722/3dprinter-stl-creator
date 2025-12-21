from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
import hashlib

from app.db.database import get_db
from app.models import Job, Artifact
from app.models.artifact import ArtifactType
from app.schemas.upload import UploadSessionCreate, UploadSessionResponse, FileUploadRequest

router = APIRouter()


@router.post("/", response_model=UploadSessionResponse)
async def create_upload_session(
    upload_request: UploadSessionCreate,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Create an upload session and generate pre-signed URLs"""
    # Verify job exists
    job = await db.get(Job, upload_request.job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    upload_session_id = f"upl_{uuid.uuid4().hex[:12]}"
    files_with_urls = []
    
    for file_info in upload_request.files:
        artifact_id = f"art_{uuid.uuid4().hex[:12]}"
        
        # TODO: Generate actual S3 pre-signed URL
        # For now, return a placeholder
        put_url = f"https://storage.example.com/upload/{upload_session_id}/{file_info.filename}"
        
        files_with_urls.append({
            "filename": file_info.filename,
            "put_url": put_url,
            "artifact_id": artifact_id
        })
    
    return {
        "upload_session_id": upload_session_id,
        "files": files_with_urls
    }


@router.post("/{upload_session_id}/complete")
async def complete_upload_session(
    upload_session_id: str,
    job_id: str,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Mark upload session as complete and create artifacts"""
    # Verify job exists
    job = await db.get(Job, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    # TODO: Verify uploads actually completed in S3
    # TODO: Create artifact records
    
    return {
        "status": "completed",
        "message": "Upload session completed successfully"
    }
