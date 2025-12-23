import asyncio
import asyncpg
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

async def test_database_connection():
    """Test database connection with the same settings as the app"""
    
    # Test direct asyncpg connection
    print("Testing direct asyncpg connection...")
    try:
        conn = await asyncpg.connect(
            host='localhost',
            port=5432,
            user='user',
            password='password',
            database='stl_generator'
        )
        print("✓ Direct asyncpg connection successful")
        
        # Test a simple query
        result = await conn.fetchval('SELECT version()')
        print(f"✓ PostgreSQL version: {result}")
        
        await conn.close()
    except Exception as e:
        print(f"✗ Direct asyncpg connection failed: {e}")
        return False
    
    # Test SQLAlchemy async engine
    print("\nTesting SQLAlchemy async engine...")
    try:
        DATABASE_URL = "postgresql+asyncpg://user:password@localhost:5432/stl_generator"
        engine = create_async_engine(DATABASE_URL, echo=True)
        
        async with engine.begin() as conn:
            result = await conn.execute("SELECT 1")
            print(f"✓ SQLAlchemy connection successful: {result.scalar()}")
        
        await engine.dispose()
    except Exception as e:
        print(f"✗ SQLAlchemy connection failed: {e}")
        return False
    
    # Test session creation
    print("\nTesting session creation...")
    try:
        DATABASE_URL = "postgresql+asyncpg://user:password@localhost:5432/stl_generator"
        engine = create_async_engine(DATABASE_URL)
        
        AsyncSessionLocal = sessionmaker(
            engine, 
            class_=AsyncSession, 
            expire_on_commit=False
        )
        
        async with AsyncSessionLocal() as session:
            result = await session.execute("SELECT 1")
            print(f"✓ Session creation successful: {result.scalar()}")
        
        await engine.dispose()
    except Exception as e:
        print(f"✗ Session creation failed: {e}")
        return False
    
    print("\n✓ All database tests passed!")
    return True

if __name__ == "__main__":
    asyncio.run(test_database_connection())
