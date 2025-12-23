"""
Automated debug script to identify database operation hang issues.
Tests each database operation individually with timeouts.
"""
import asyncio
import sys
import os

# Add the backend to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_with_timeout(coro, timeout_seconds, test_name):
    """Run a coroutine with a timeout and report results."""
    print(f"\n[TEST] {test_name}...")
    try:
        result = await asyncio.wait_for(coro, timeout=timeout_seconds)
        print(f"  ✓ PASSED in <{timeout_seconds}s")
        return result
    except asyncio.TimeoutError:
        print(f"  ✗ FAILED - Timed out after {timeout_seconds}s")
        return None
    except Exception as e:
        print(f"  ✗ FAILED - Error: {e}")
        return None

async def main():
    print("=" * 60)
    print("DATABASE OPERATION DEBUG TEST")
    print("=" * 60)
    
    # Test 1: Import settings
    print("\n[TEST] Importing settings...")
    try:
        from app.core.config import settings
        print(f"  ✓ DATABASE_URL: {settings.DATABASE_URL}")
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        return
    
    # Test 2: Create engine
    print("\n[TEST] Creating SQLAlchemy engine...")
    try:
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from sqlalchemy.orm import sessionmaker
        
        if settings.DATABASE_URL.startswith("postgresql://"):
            db_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
        else:
            db_url = settings.DATABASE_URL
        
        print(f"  Using URL: {db_url}")
        engine = create_async_engine(db_url, echo=False)
        print(f"  ✓ Engine created")
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        return
    
    # Test 3: Create tables
    async def create_tables():
        from app.models.base import Base
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        return True
    
    result = await test_with_timeout(create_tables(), 5, "Creating database tables")
    if result is None:
        print("  ! Table creation failed or timed out")
    
    # Test 4: Create session
    print("\n[TEST] Creating session...")
    try:
        AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        print(f"  ✓ Session factory created")
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        return
    
    # Test 5: Simple SELECT query
    async def test_select():
        async with AsyncSessionLocal() as session:
            from sqlalchemy import text
            result = await session.execute(text("SELECT 1"))
            return result.scalar()
    
    result = await test_with_timeout(test_select(), 3, "Simple SELECT query")
    
    # Test 6: Create a project object (no commit)
    async def test_create_object():
        from app.models import Project
        import uuid
        project = Project(
            id=f"test_{uuid.uuid4().hex[:8]}",
            user_id="test_user",
            name="Test Project",
            description="Testing"
        )
        return project
    
    project = await test_with_timeout(test_create_object(), 2, "Creating Project object")
    
    # Test 7: Add to session (no commit)
    async def test_add_to_session():
        async with AsyncSessionLocal() as session:
            from app.models import Project
            import uuid
            project = Project(
                id=f"test_{uuid.uuid4().hex[:8]}",
                user_id="test_user",
                name="Test Add",
                description="Testing add"
            )
            session.add(project)
            return True
    
    result = await test_with_timeout(test_add_to_session(), 3, "Adding object to session (no commit)")
    
    # Test 8: Full INSERT with commit - THIS IS THE KEY TEST
    async def test_insert_with_commit():
        async with AsyncSessionLocal() as session:
            from app.models import Project
            import uuid
            project = Project(
                id=f"test_{uuid.uuid4().hex[:8]}",
                user_id="test_user",
                name="Test Insert",
                description="Testing insert with commit"
            )
            session.add(project)
            await session.commit()
            await session.refresh(project)
            return project.id
    
    result = await test_with_timeout(test_insert_with_commit(), 5, "INSERT with COMMIT (key test)")
    if result:
        print(f"  Created project ID: {result}")
    
    # Test 9: Check if LocalWorker is blocking
    print("\n[TEST] Checking LocalWorker status...")
    try:
        from app.services.local_worker import local_worker
        print(f"  LocalWorker running: {local_worker._running}")
        print(f"  LocalWorker task: {local_worker._task}")
    except Exception as e:
        print(f"  Could not check LocalWorker: {e}")
    
    # Test 10: List projects
    async def test_list_projects():
        async with AsyncSessionLocal() as session:
            from sqlalchemy import select
            from app.models import Project
            result = await session.execute(select(Project).limit(5))
            projects = result.scalars().all()
            return len(projects)
    
    result = await test_with_timeout(test_list_projects(), 3, "SELECT projects (list)")
    if result is not None:
        print(f"  Found {result} projects")
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)
    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
