import asyncio
import os
import sys
from sqlalchemy import select

# Add current directory to path
sys.path.append(os.getcwd())

from app.db.database import AsyncSessionLocal
from app.models.printer_profile import PrinterProfile, PrinterType
from app.models.model_preset import ModelPreset, PresetCategory, MiniScalePreset, BasePreset, PoseCategory, DetailDensity

async def seed():
    print("Seeding database with default printer profiles and presets...")
    async with AsyncSessionLocal() as session:
        # Check if already seeded
        result = await session.execute(select(PrinterProfile).where(PrinterProfile.id == "pp_default_fdm"))
        if result.scalar_one_or_none():
            print("Database already contains default profiles. Skipping.")
            return

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
        
        session.add(fdm_profile)
        session.add(resin_profile)
        session.add(mini_28mm_preset)
        
        await session.commit()
        print("Database seeded successfully!")

if __name__ == "__main__":
    asyncio.run(seed())
