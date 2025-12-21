from enum import Enum
from typing import Optional, List, Dict, Any, TYPE_CHECKING
from sqlalchemy import String, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, IdMixin, TimestampMixin

if TYPE_CHECKING:
    from .job import Job


class ValidationScope(str, Enum):
    INPUT = "INPUT"
    MESH = "MESH"
    PRINTABILITY = "PRINTABILITY"
    SAFETY = "SAFETY"


class ValidationStatus(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


class FindingSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class ValidationReport(Base, IdMixin, TimestampMixin):
    __tablename__ = "validation_reports"
    
    job_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("jobs.id"), nullable=False
    )
    scope: Mapped[ValidationScope] = mapped_column(String(20), nullable=False)
    status: Mapped[ValidationStatus] = mapped_column(String(10), nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    
    # Relationships
    job: Mapped["Job"] = relationship("Job", back_populates="validation_reports")
    findings: Mapped[List["ValidationFinding"]] = relationship(
        "ValidationFinding", back_populates="report", cascade="all, delete-orphan"
    )


class ValidationFinding(Base, IdMixin, TimestampMixin):
    __tablename__ = "validation_findings"
    
    report_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("validation_reports.id"), nullable=False
    )
    severity: Mapped[FindingSeverity] = mapped_column(String(10), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)  # Stable identifier
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message_plain: Mapped[str] = mapped_column(String(1000), nullable=False)
    
    # Metrics
    metric_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    metric_value: Mapped[Optional[float]] = mapped_column(JSON, nullable=True)
    threshold: Mapped[Optional[float]] = mapped_column(JSON, nullable=True)
    
    # Recommended action
    recommended_action: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    action_payload: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    
    # Related artifact
    related_artifact_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    
    # Relationships
    report: Mapped["ValidationReport"] = relationship("ValidationReport", back_populates="findings")
