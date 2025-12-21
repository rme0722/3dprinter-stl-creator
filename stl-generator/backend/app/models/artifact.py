from enum import Enum
from typing import Optional, Dict, Any, TYPE_CHECKING
from sqlalchemy import String, ForeignKey, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, IdMixin, TimestampMixin

if TYPE_CHECKING:
    from .project import Project
    from .job import Job


class ArtifactType(str, Enum):
    # Input artifacts
    RAW_PHOTO = "RAW_PHOTO"
    RAW_IMAGE = "RAW_IMAGE"
    
    # Processing artifacts
    ANALYSIS_REPORT_JSON = "ANALYSIS_REPORT_JSON"
    MASK_IMAGE = "MASK_IMAGE"
    DEPTH_MAP = "DEPTH_MAP"
    POINT_CLOUD_SPARSE = "POINT_CLOUD_SPARSE"
    POINT_CLOUD_DENSE = "POINT_CLOUD_DENSE"
    
    # Mesh artifacts
    MESH_RAW = "MESH_RAW"
    MESH_CLEANED = "MESH_CLEANED"
    MESH_REPAIRED = "MESH_REPAIRED"
    MESH_SCALED_MM = "MESH_SCALED_MM"
    MESH_HOLLOWED = "MESH_HOLLOWED"
    MESH_SUPPORTED = "MESH_SUPPORTED"
    
    # Output artifacts
    PREVIEW_GLB = "PREVIEW_GLB"
    FINAL_STL = "FINAL_STL"
    VALIDATION_REPORT_JSON = "VALIDATION_REPORT_JSON"


class ArtifactFormat(str, Enum):
    JPG = "jpg"
    PNG = "png"
    PLY = "ply"
    OBJ = "obj"
    GLB = "glb"
    STL = "stl"
    JSON = "json"
    ZIP = "zip"


class Artifact(Base, IdMixin, TimestampMixin):
    __tablename__ = "artifacts"
    
    # Foreign keys
    job_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("jobs.id"), nullable=False
    )
    project_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("projects.id"), nullable=False
    )
    
    # Core fields
    artifact_type: Mapped[ArtifactType] = mapped_column(String(50), nullable=False)
    format: Mapped[ArtifactFormat] = mapped_column(String(10), nullable=False)
    uri: Mapped[str] = mapped_column(String(500), nullable=False)  # S3/object storage path
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Versioning and labeling
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    label: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Metadata (dimensions, units, triangle count, etc.)
    metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    
    # Relationships
    job: Mapped["Job"] = relationship("Job", back_populates="artifacts")
    project: Mapped["Project"] = relationship("Project", back_populates="artifacts")
