from enum import Enum
from datetime import datetime
from typing import List, Optional, Dict, Any, TYPE_CHECKING
from sqlalchemy import String, ForeignKey, Float, JSON, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, IdMixin, TimestampMixin

if TYPE_CHECKING:
    from .project import Project
    from .artifact import Artifact
    from .validation import ValidationReport


class PipelineType(str, Enum):
    SCAN = "SCAN"
    RELIEF = "RELIEF"
    GENERATIVE = "GENERATIVE"


class JobState(str, Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    VALIDATING = "VALIDATING"
    ACTION_REQUIRED = "ACTION_REQUIRED"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class SafetyStatus(str, Enum):
    PASS = "PASS"
    BLOCK = "BLOCK"
    REVIEW = "REVIEW"


class Job(Base, IdMixin, TimestampMixin):
    __tablename__ = "jobs"
    
    # Core fields
    project_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("projects.id"), nullable=False
    )
    pipeline_type: Mapped[PipelineType] = mapped_column(String(20), nullable=False)
    state: Mapped[JobState] = mapped_column(String(20), nullable=False, default=JobState.DRAFT)
    hold_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Configuration
    config: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default={})
    model_preset_id: Mapped[Optional[str]] = mapped_column(
        String(64), ForeignKey("model_presets.id"), nullable=True
    )
    printer_profile_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("printer_profiles.id"), nullable=False
    )
    
    # Timestamps
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Error handling
    error_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    
    # Safety and quality
    safety_status: Mapped[Optional[SafetyStatus]] = mapped_column(String(20), nullable=True)
    safety_summary: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    quality_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    quality_score_version: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    quality_summary: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    
    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="jobs")
    artifacts: Mapped[List["Artifact"]] = relationship(
        "Artifact", back_populates="job", cascade="all, delete-orphan"
    )
    validation_reports: Mapped[List["ValidationReport"]] = relationship(
        "ValidationReport", back_populates="job", cascade="all, delete-orphan"
    )
    
    def can_transition_to(self, new_state: JobState) -> bool:
        """Check if state transition is allowed"""
        allowed_transitions = {
            JobState.DRAFT: [JobState.SUBMITTED, JobState.CANCELLED],
            JobState.SUBMITTED: [JobState.VALIDATING, JobState.CANCELLED],
            JobState.VALIDATING: [JobState.ACTION_REQUIRED, JobState.QUEUED, JobState.FAILED, JobState.CANCELLED],
            JobState.ACTION_REQUIRED: [JobState.VALIDATING, JobState.CANCELLED],
            JobState.QUEUED: [JobState.RUNNING, JobState.CANCELLED],
            JobState.RUNNING: [JobState.REVIEW_REQUIRED, JobState.SUCCEEDED, JobState.FAILED, JobState.CANCELLED],
            JobState.REVIEW_REQUIRED: [JobState.RUNNING, JobState.SUCCEEDED, JobState.CANCELLED],
            JobState.SUCCEEDED: [],
            JobState.FAILED: [],
            JobState.CANCELLED: []
        }
        return new_state in allowed_transitions.get(self.state, [])
