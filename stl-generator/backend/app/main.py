from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import time
import logging
import time
import json
from pathlib import Path

from app.core.config import settings
from app.api.v1.api import api_router
from app.db.database import engine, Base
from app.services.local_worker import local_worker

# Configure debug logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('debug.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log_path = Path('debug.log')
    if log_path.exists():
        try:
            log_path.unlink()
        except Exception:
            pass
        
    # Startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Start local worker for job processing
    await local_worker.start()
    
    yield
    
    # Shutdown
    await local_worker.stop()
    await engine.dispose()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
    redirect_slashes=False  # Prevent 307 redirects that break CORS with proxy
)

# Request/Response logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    
    # Log request details (don't read body - it consumes the stream and breaks POST requests)
    logger.info(f"=== INCOMING REQUEST ===")
    logger.info(f"Method: {request.method}")
    logger.info(f"URL: {request.url}")
    logger.info(f"Path params: {request.path_params}")
    logger.info(f"Query params: {dict(request.query_params)}")
    
    # Process request
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        
        # Log response details
        logger.info(f"=== RESPONSE ===")
        logger.info(f"Status: {response.status_code}")
        logger.info(f"Process time: {process_time:.4f}s")
        
        return response
    except Exception as e:
        process_time = time.time() - start_time
        logger.error(f"=== REQUEST FAILED ===")
        logger.error(f"Error: {str(e)}")
        logger.error(f"Process time: {process_time:.4f}s")
        raise

# Set up CORS - always enable for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": settings.VERSION}
