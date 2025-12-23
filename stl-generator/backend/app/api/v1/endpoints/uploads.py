from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
import hashlib
from pathlib import Path

from app.db.database import get_db
from app.models import Job, Artifact
from app.models.artifact import ArtifactType
from app.schemas.upload import UploadSessionCreate, UploadSessionResponse, FileUploadRequest
from app.services.local_storage import save_file, get_file_path, STORAGE_BASE

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


@router.post("/file/{job_id}")
async def upload_file_direct(
    job_id: str,
    file: UploadFile = File(...),
    artifact_type: str = Form("RAW_IMAGE"),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Direct file upload endpoint for local development.
    Uploads a file and creates an artifact record.
    """
    # Verify job exists
    job = await db.get(Job, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    # Read file content
    content = await file.read()
    
    # Determine artifact type
    try:
        art_type = ArtifactType(artifact_type)
    except ValueError:
        art_type = ArtifactType.SOURCE_IMAGE
    
    # Determine format from filename
    filename = file.filename or "upload"
    format_ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else "bin"
    
    # Save to local storage (returns URI string, not Path)
    uri, sha256_hash, size_bytes = await save_file(
        content=content,
        category="inputs",
        job_id=job_id,
        filename=filename
    )
    
    # Create artifact record - uri is already in correct format from save_file
    artifact = Artifact(
        id=f"art_{uuid.uuid4().hex[:12]}",
        job_id=job_id,
        project_id=job.project_id,
        artifact_type=art_type,
        format=format_ext,
        uri=uri,
        sha256=sha256_hash,
        size_bytes=size_bytes,
        version=1,
        label=f"Input: {filename}",
        metadata_json={"original_filename": filename}
    )
    db.add(artifact)
    await db.commit()
    await db.refresh(artifact)
    
    return {
        "artifact_id": artifact.id,
        "filename": filename,
        "size_bytes": size_bytes,
        "uri": uri
    }


@router.get("/file/{artifact_id}/download")
async def download_artifact(
    artifact_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Download an artifact file."""
    artifact = await db.get(Artifact, artifact_id)
    if not artifact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artifact not found"
        )
    
    file_path = get_file_path(artifact.uri)
    if not file_path or not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found in storage"
        )
    
    # Determine filename for download
    original_filename = artifact.metadata_json.get("original_filename") if artifact.metadata_json else None
    download_filename = original_filename or f"{artifact.label or artifact.id}.{artifact.format}"
    
    return FileResponse(
        path=file_path,
        filename=download_filename,
        media_type=f"application/{artifact.format}"
    )
