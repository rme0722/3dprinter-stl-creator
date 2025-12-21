"""Initialize database with default data"""
import asyncio
import sys
from pathlib import Path
import uuid
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.models.base import Base
from app.models.printer_profile import PrinterProfile, PrinterType
from app.models.model_preset import ModelPreset, PresetCategory, MiniScalePreset, BasePreset, PoseCategory, DetailDensity

DATABASE_URL = "postgresql+asyncpg://user:password@localhost:5432/stl_generator"

async def init_db():
    """Initialize database with default data"""
    engine = create_async_engine(DATABASE_URL, echo=True)
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create session
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with AsyncSessionLocal() as session:
        # Add default printer profiles
        fdm_profile = PrinterProfile(
            id=f"pp_default_fdm",
            user_id=None,  # System default
            name="Default FDM Printer",
            printer_type=PrinterType.FDM,
            settings={
                "nozzle_diameter_mm": 0.4,
                "layer_height_mm": 0.2,
                "build_volume_mm": [220, 220, 250],
                "min_wall_thickness_mm": 0.8,
                "support_overhang_angle": 45
            }
        )
        
        resin_profile = PrinterProfile(
            id=f"pp_default_resin",
            user_id=None,  # System default
            name="Default Resin Printer",
            printer_type=PrinterType.RESIN,
            settings={
                "pixel_size_mm": 0.047,
                "layer_height_mm": 0.05,
                "build_volume_mm": [120, 68, 150],
                "min_wall_thickness_mm": 0.4,
                "exposure_time_s": 2.5
            }
        )
        
        # Add default model presets for minis
        mini_28mm_preset = ModelPreset(
            id=f"mp_mini_28mm",
            user_id=None,  # System default
            name="28mm Heroic Mini",
            category=PresetCategory.MINI,
            mini_scale_preset=MiniScalePreset.MINI_28MM_HEROIC,
            base_preset=BasePreset.ROUND_25MM,
            pose_category=PoseCategory.IDLE,
            detail_density=DetailDensity.MED,
            default_config={
                "scale_mm": 28,
                "base_height_mm": 2,
                "base_diameter_mm": 25
            }
        )
        
        mini_32mm_preset = ModelPreset(
            id=f"mp_mini_32mm",
            user_id=None,  # System default
            name="32mm Standard Mini",
            category=PresetCategory.MINI,
            mini_scale_preset=MiniScalePreset.MINI_32MM,
            base_preset=BasePreset.ROUND_32MM,
            pose_category=PoseCategory.IDLE,
            detail_density=DetailDensity.HIGH,
            default_config={
                "scale_mm": 32,
                "base_height_mm": 3,
                "base_diameter_mm": 32
            }
        )
        
        session.add(fdm_profile)
        session.add(resin_profile)
        session.add(mini_28mm_preset)
        session.add(mini_32mm_preset)
        
        await session.commit()
        print("Database initialized with default data!")
    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(init_db())
