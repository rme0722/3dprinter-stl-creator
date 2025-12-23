import asyncio
import asyncpg

async def simple_test():
    """Simple database connection test"""
    print("Testing database connection...")
    
    try:
        # Test connection with timeout
        conn = await asyncio.wait_for(
            asyncpg.connect(
                host='localhost',
                port=5432,
                user='user',
                password='password',
                database='stl_generator'
            ),
            timeout=5.0  # 5 second timeout
        )
        print("✓ Connection successful!")
        await conn.close()
        return True
    except asyncio.TimeoutError:
        print("✗ Connection timed out after 5 seconds")
        return False
    except asyncpg.InvalidCatalogNameError:
        print("✗ Database 'stl_generator' does not exist")
        return False
    except asyncpg.InvalidPasswordError:
        print("✗ Invalid username or password")
        return False
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(simple_test())
