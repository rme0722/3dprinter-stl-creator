import asyncio
import os
import sys
from sqlalchemy import select

# Add current directory to path
sys.path.append(os.getcwd())

from app.db.database import AsyncSessionLocal
from app.models.printer_profile import PrinterProfile

async def check():
    print("Checking database for printer profiles...")
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(PrinterProfile))
            profiles = result.scalars().all()
            print(f"Total profiles found: {len(profiles)}")
            for p in profiles:
                print(f"- {p.name} (ID: {p.id})")
    except Exception as e:
        print(f"Error checking database: {e}")

if __name__ == "__main__":
    asyncio.run(check())
