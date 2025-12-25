import asyncio
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "app"))

from sqlalchemy import select
from app.db.session import async_session_factory
from app.models.artifact import Artifact

async def check():
    async with async_session_factory() as db:
        res = await db.execute(select(Artifact))
        arts = res.scalars().all()
        print(f"Total artifacts: {len(arts)}")
        for a in arts:
            print(f"- {a.artifact_type} {a.uri}")

if __name__ == "__main__":
    asyncio.run(check())
