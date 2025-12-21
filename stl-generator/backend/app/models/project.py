from typing import List, TYPE_CHECKING
from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, IdMixin, TimestampMixin

if TYPE_CHECKING:
    from .job import Job
    from .artifact import Artifact


class Project(Base, IdMixin, TimestampMixin):
    __tablename__ = "projects"
    
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(String(1000), nullable=True)
    
    # Relationships
    jobs: Mapped[List["Job"]] = relationship(
        "Job", back_populates="project", cascade="all, delete-orphan"
    )
    artifacts: Mapped[List["Artifact"]] = relationship(
        "Artifact", back_populates="project", cascade="all, delete-orphan"
    )
