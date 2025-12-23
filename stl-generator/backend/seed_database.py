"""
Seed the database with required default data.
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def seed_database():
    from app.db.database import AsyncSessionLocal, engine
    from app.models.base import Base
    from app.models import PrinterProfile
    from sqlalchemy import select
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Seed default printer profile
    async with AsyncSessionLocal() as session:
        # Check if profile already exists
        result = await session.execute(
            select(PrinterProfile).where(PrinterProfile.id == "pp_default_fdm")
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            print("Default printer profile already exists")
        else:
            from app.models.printer_profile import PrinterType
            profile = PrinterProfile(
                id="pp_default_fdm",
                name="Default FDM Printer",
                printer_type=PrinterType.FDM,
                settings={
                    "build_volume_x": 220.0,
                    "build_volume_y": 220.0,
                    "build_volume_z": 250.0,
                    "nozzle_diameter": 0.4,
                    "layer_height_min": 0.1,
                    "layer_height_max": 0.3,
                }
            )
            session.add(profile)
            await session.commit()
            print(f"Created default printer profile: {profile.id}")
    
    await engine.dispose()
    print("Database seeding complete!")

if __name__ == "__main__":
    asyncio.run(seed_database())
