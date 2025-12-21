from enum import Enum
from typing import Optional, Dict, Any
from sqlalchemy import String, JSON
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, IdMixin, TimestampMixin


class PresetCategory(str, Enum):
    MINI = "MINI"


class MiniScalePreset(str, Enum):
    MINI_28MM_HEROIC = "MINI_28MM_HEROIC"
    MINI_32MM = "MINI_32MM"


class BasePreset(str, Enum):
    ROUND_25MM = "ROUND_25MM"
    ROUND_32MM = "ROUND_32MM"
    ROUND_40MM = "ROUND_40MM"
    NONE = "NONE"


class PoseCategory(str, Enum):
    IDLE = "IDLE"
    CHARGING = "CHARGING"
    AIMING = "AIMING"
    LEADER = "LEADER"


class DetailDensity(str, Enum):
    LOW = "LOW"
    MED = "MED"
    HIGH = "HIGH"


class ModelPreset(Base, IdMixin, TimestampMixin):
    __tablename__ = "model_presets"
    
    user_id: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, index=True
    )  # Null for system presets
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[PresetCategory] = mapped_column(String(20), nullable=False)
    
    # Mini-specific presets
    mini_scale_preset: Mapped[Optional[MiniScalePreset]] = mapped_column(String(30), nullable=True)
    base_preset: Mapped[Optional[BasePreset]] = mapped_column(String(20), nullable=True)
    pose_category: Mapped[Optional[PoseCategory]] = mapped_column(String(20), nullable=True)
    detail_density: Mapped[Optional[DetailDensity]] = mapped_column(String(10), nullable=True)
    
    # Pipeline-specific defaults
    default_config: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default={})
