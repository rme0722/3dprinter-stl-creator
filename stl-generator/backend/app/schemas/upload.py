from typing import List
from pydantic import BaseModel
from app.models.artifact import ArtifactType


class FileUploadRequest(BaseModel):
    filename: str
    content_type: str
    size_bytes: int
    sha256: str


class UploadSessionCreate(BaseModel):
    job_id: str
    artifact_type: ArtifactType
    files: List[FileUploadRequest]


class FileUploadResponse(BaseModel):
    filename: str
    put_url: str
    artifact_id: str


class UploadSessionResponse(BaseModel):
    upload_session_id: str
    files: List[FileUploadResponse]
