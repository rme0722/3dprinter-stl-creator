import asyncio
import os
import sys
from sqlalchemy import select

# Add current directory to path
sys.path.append(os.getcwd())

from app.db.database import AsyncSessionLocal
from app.models.project import Project

async def check():
    print("Checking database for projects...")
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Project))
            projects = result.scalars().all()
            print(f"Total projects found: {len(projects)}")
            for p in projects:
                print(f"- {p.name} (ID: {p.id})")
    except Exception as e:
        print(f"Error checking database: {e}")

if __name__ == "__main__":
    asyncio.run(check())
