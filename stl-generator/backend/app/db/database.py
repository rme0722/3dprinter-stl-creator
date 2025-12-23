from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import event
from typing import AsyncGenerator

from app.core.config import settings
from app.models.base import Base

# Handle both PostgreSQL and SQLite URLs
if settings.DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
else:
    DATABASE_URL = settings.DATABASE_URL

# SQLite-specific configuration for better concurrency
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {
        "check_same_thread": False,
        "timeout": 30,  # Wait up to 30 seconds for locks
    }

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    connect_args=connect_args,
)

AsyncSessionLocal = sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
