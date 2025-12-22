from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from pydantic.config import ConfigDict
from app.models.artifact import ArtifactType, ArtifactFormat


class ArtifactBase(BaseModel):
    artifact_type: ArtifactType
    format: ArtifactFormat
    label: Optional[str] = None


class ArtifactCreate(ArtifactBase):
    uri: str
    sha256: str
    size_bytes: int
    metadata: Optional[Dict[str, Any]] = None


class ArtifactResponse(ArtifactBase):
    id: str
    job_id: str
    project_id: str
    uri: str
    sha256: str
    size_bytes: int
    version: int
    metadata: Optional[Dict[str, Any]] = Field(default=None, validation_alias="metadata_json")
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
