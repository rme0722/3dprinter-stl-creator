"""
Test database operations with LocalWorker running concurrently.
This simulates the actual server environment.
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def main():
    print("=" * 60)
    print("CONCURRENT DATABASE TEST (with LocalWorker)")
    print("=" * 60)
    
    # Import after path setup
    from app.services.local_worker import local_worker
    from app.db.database import AsyncSessionLocal, engine
    from app.models.base import Base
    from app.models import Project
    from sqlalchemy import select
    import uuid
    
    # Create tables
    print("\n[1] Creating tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("  ✓ Tables created")
    
    # Start LocalWorker
    print("\n[2] Starting LocalWorker...")
    await local_worker.start()
    print(f"  LocalWorker running: {local_worker._running}")
    
    # Wait a moment for worker to start polling
    await asyncio.sleep(1)
    
    # Test project creation while worker is running
    print("\n[3] Testing project creation with worker running...")
    try:
        async with AsyncSessionLocal() as session:
            project = Project(
                id=f"concurrent_test_{uuid.uuid4().hex[:8]}",
                user_id="test_user",
                name="Concurrent Test Project",
                description="Testing with LocalWorker running"
            )
            session.add(project)
            
            # This is the critical test - commit while worker is polling
            await asyncio.wait_for(session.commit(), timeout=5)
            await session.refresh(project)
            print(f"  ✓ Project created: {project.id}")
    except asyncio.TimeoutError:
        print("  ✗ FAILED - Commit timed out after 5s (database lock issue)")
    except Exception as e:
        print(f"  ✗ FAILED - Error: {e}")
    
    # Test listing projects
    print("\n[4] Testing project listing...")
    try:
        async with AsyncSessionLocal() as session:
            result = await asyncio.wait_for(
                session.execute(select(Project).limit(10)),
                timeout=3
            )
            projects = result.scalars().all()
            print(f"  ✓ Found {len(projects)} projects")
    except Exception as e:
        print(f"  ✗ FAILED - Error: {e}")
    
    # Stop LocalWorker
    print("\n[5] Stopping LocalWorker...")
    await local_worker.stop()
    print(f"  LocalWorker running: {local_worker._running}")
    
    # Cleanup
    await engine.dispose()
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
