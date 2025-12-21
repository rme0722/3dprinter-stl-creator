from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel
from app.models.job import PipelineType, JobState, SafetyStatus


class JobBase(BaseModel):
    pipeline_type: PipelineType
    printer_profile_id: str
    model_preset_id: Optional[str] = None
    config: Optional[Dict[str, Any]] = {}


class JobCreate(JobBase):
    pass


class JobUpdate(BaseModel):
    config: Optional[Dict[str, Any]] = None
    model_preset_id: Optional[str] = None
    printer_profile_id: Optional[str] = None


class JobSubmit(BaseModel):
    pass


class QualitySummary(BaseModel):
    input_quality: float
    reconstruction_confidence: float
    printability_risk: float
    notes: Optional[list[str]] = []


class JobResponse(JobBase):
    id: str
    project_id: str
    state: JobState
    hold_reason: Optional[str] = None
    submitted_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    safety_status: Optional[SafetyStatus] = None
    safety_summary: Optional[Dict[str, Any]] = None
    quality_score: Optional[float] = None
    quality_score_version: Optional[str] = None
    quality_summary: Optional[QualitySummary] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
