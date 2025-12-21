from enum import Enum
from typing import Optional, Dict, Any
from sqlalchemy import String, JSON
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, IdMixin, TimestampMixin


class PrinterType(str, Enum):
    FDM = "FDM"
    RESIN = "RESIN"


class PrinterProfile(Base, IdMixin, TimestampMixin):
    __tablename__ = "printer_profiles"
    
    user_id: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, index=True
    )  # Null for system defaults
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    printer_type: Mapped[PrinterType] = mapped_column(String(10), nullable=False)
    
    # Settings: nozzle/pixel size, layer height, build volume, etc.
    settings: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default={})
