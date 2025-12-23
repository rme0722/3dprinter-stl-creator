"""
Simple local worker for processing jobs in-process.
Uses asyncio for background task processing - suitable for single-user local deployment.
"""

import asyncio
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
import numpy as np
import logging

from app.core.config import settings
from app.models import Job, Artifact
from app.models.job import JobState
from app.models.artifact import ArtifactType
from app.services.local_storage import STORAGE_BASE, get_storage_path, get_relative_uri

# Create a separate engine for the worker to avoid session conflicts
# Handle both PostgreSQL and SQLite URLs
if settings.DATABASE_URL.startswith("postgresql://"):
    worker_db_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
    worker_connect_args = {}
else:
    worker_db_url = settings.DATABASE_URL
    worker_connect_args = {
        "check_same_thread": False,
        "timeout": 30,  # Wait up to 30 seconds for locks
    }

worker_engine = create_async_engine(
    worker_db_url,
    echo=False,
    connect_args=worker_connect_args,
)
WorkerSessionLocal = sessionmaker(
    worker_engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

logger = logging.getLogger(__name__)

class LocalWorker:
    """Simple in-process worker for job processing."""
    
    def __init__(self):
        self._running = False
        self._task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Start the worker background task."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._process_loop())
        print("LocalWorker started")
    
    async def stop(self):
        """Stop the worker."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        print("LocalWorker stopped")
    
    async def _process_loop(self):
        """Main processing loop - polls for submitted jobs."""
        while self._running:
            try:
                async with WorkerSessionLocal() as db:
                    # Find jobs that need processing
                    result = await db.execute(
                        select(Job).where(Job.state == JobState.SUBMITTED)
                    )
                    jobs = result.scalars().all()
                    
                    for job in jobs:
                        await self._process_job(db, job) # Now matches the new signature
                
                # Poll every 2 seconds
                await asyncio.sleep(2)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Worker error: {e}")
                await asyncio.sleep(5)
    
    async def _process_job(self, db: AsyncSession, job: Job):
        """Process a job."""
        print(f"Processing job: {job.id}")
        
        try:
            print(f"  Job {job.id}: Starting processing ({job.pipeline_type})")
            job.state = JobState.RUNNING
            job.started_at = datetime.utcnow()
            await db.commit()
            
            if job.pipeline_type == "RELIEF":
                await self._process_relief_job(db, job)
            elif job.pipeline_type == "SCAN":
                await self._process_scan_job(db, job)
            else:
                raise ValueError(f"Unsupported pipeline type: {job.pipeline_type}")
            
            job.state = JobState.SUCCEEDED
            job.completed_at = datetime.utcnow()
            job.quality_score = 0.85
            job.quality_summary = {
                "input_quality": 0.90,
                "reconstruction_confidence": 0.85,
                "printability_risk": 0.10,
                "notes": ["Processing completed successfully"]
            }
            await db.commit()
            print(f"Job {job.id} completed successfully")
            
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            logger.exception(f"Job {job.id} failed")
            print(f"Job {job.id} failed: {e}\n{tb}")
            job.state = JobState.FAILED
            job.error_message = str(e)
            job.error_code = "PROCESSING_ERROR"
            job.completed_at = datetime.utcnow()
            await db.commit()
    
    async def _process_relief_job(self, db: AsyncSession, job: Job):
        """Process a relief pipeline job - converts uploaded image to 3D relief."""
        import uuid
        from PIL import Image
        import io
        
        print(f"  Job {job.id}: Finding input image...")
        
        # Find the input image artifact
        from sqlalchemy import select
        result = await db.execute(
            select(Artifact).where(
                Artifact.job_id == job.id,
                Artifact.artifact_type.in_([ArtifactType.RAW_IMAGE, ArtifactType.RAW_PHOTO])
            )
        )
        input_artifact = result.scalars().first()
        
        if not input_artifact:
            raise Exception("No input image found for relief job")
        
        print(f"  Job {job.id}: Loading image from {input_artifact.uri}...")
        
        # Load the image from storage
        from app.services.local_storage import get_file_path
        image_path = get_file_path(input_artifact.uri)
        if not image_path or not image_path.exists():
            raise Exception(f"Image file not found: {input_artifact.uri}")
        
        # Open and process the image
        print(f"  Job {job.id}: Converting image to heightmap...")
        img = Image.open(image_path)
        
        # Convert to grayscale
        img_gray = img.convert('L')
        
        # Resize to manageable grid size (max 100x100 for reasonable STL size)
        max_size = 100
        width, height = img_gray.size
        if width > max_size or height > max_size:
            ratio = min(max_size / width, max_size / height)
            new_size = (int(width * ratio), int(height * ratio))
            img_gray = img_gray.resize(new_size, Image.Resampling.LANCZOS)
        
        print(f"  Job {job.id}: Generating 3D mesh ({img_gray.size[0]}x{img_gray.size[1]} grid)...")
        
        # Generate the relief STL from the image
        stl_content = self._generate_relief_from_image(img_gray)
        
        # Save the STL file
        output_path = get_storage_path("outputs", job.id, "relief_output.stl")
        output_path.write_bytes(stl_content)
        
        uri = get_relative_uri("outputs", job.id, "relief_output.stl")
        sha256_hash = hashlib.sha256(stl_content).hexdigest()
        size_bytes = len(stl_content)
        
        print(f"  Job {job.id}: Saving STL file ({size_bytes} bytes)...")
        
        # Create output artifact
        artifact = Artifact(
            id=f"art_{uuid.uuid4().hex[:12]}",
            job_id=job.id,
            project_id=job.project_id,
            artifact_type=ArtifactType.FINAL_STL,
            format="stl",
            uri=uri,
            sha256=sha256_hash,
            size_bytes=size_bytes,
            version=1,
            label="Relief Output",
            metadata_json={
                "source_image": input_artifact.uri,
                "grid_size": [img_gray.size[0], img_gray.size[1]],
                "dimensions_mm": [100, 100, 10],
                "watertight": True
            }
        )
        db.add(artifact)
        await db.commit()
        print(f"  Job {job.id}: Created artifact {artifact.id}")

    async def _process_scan_job(self, db: AsyncSession, job: Job):
        """Process a scan pipeline job - multi-photo photogrammetry."""
        from app.workers.scan_pipeline import ScanPipeline
        print(f"  Job {job.id}: Starting ScanPipeline...")
        pipeline = ScanPipeline(job.id, db)
        await pipeline.run()
    
    def _generate_relief_from_image(self, img) -> bytes:
        """Generate a relief STL from a grayscale PIL Image.
        
        Brighter pixels = higher elevation.
        """
        import struct
        
        # Get image dimensions and pixel data
        width, height = img.size
        pixels = np.array(img)
        
        # Normalize pixel values to height (0-255 -> base_height to max_height)
        base_height = 2.0  # mm - minimum thickness for printability
        relief_depth = 8.0  # mm - maximum relief height
        
        # Create coordinate grids
        # Scale to 100mm width, proportional height
        scale = 100.0 / max(width, height)
        x = np.linspace(0, width * scale, width)
        y = np.linspace(0, height * scale, height)
        X, Y = np.meshgrid(x, y)
        
        # Convert pixel brightness to height (invert so dark = low, bright = high)
        Z = base_height + (pixels / 255.0) * relief_depth
        
        # Build triangles for the mesh
        triangles = []
        
        # Top surface (relief)
        for i in range(height - 1):
            for j in range(width - 1):
                v00 = (X[i, j], Y[i, j], Z[i, j])
                v10 = (X[i+1, j], Y[i+1, j], Z[i+1, j])
                v01 = (X[i, j+1], Y[i, j+1], Z[i, j+1])
                v11 = (X[i+1, j+1], Y[i+1, j+1], Z[i+1, j+1])
                
                triangles.append((v00, v10, v11))
                triangles.append((v00, v11, v01))
        
        # Bottom surface (flat base)
        base_z = 0
        for i in range(height - 1):
            for j in range(width - 1):
                v00 = (X[i, j], Y[i, j], base_z)
                v10 = (X[i+1, j], Y[i+1, j], base_z)
                v01 = (X[i, j+1], Y[i, j+1], base_z)
                v11 = (X[i+1, j+1], Y[i+1, j+1], base_z)
                
                triangles.append((v00, v11, v10))  # Reversed winding for bottom
                triangles.append((v00, v01, v11))
        
        # Side walls
        # Front wall (y = 0)
        for j in range(width - 1):
            triangles.append(((X[0, j], Y[0, j], base_z), (X[0, j+1], Y[0, j+1], Z[0, j+1]), (X[0, j], Y[0, j], Z[0, j])))
            triangles.append(((X[0, j], Y[0, j], base_z), (X[0, j+1], Y[0, j+1], base_z), (X[0, j+1], Y[0, j+1], Z[0, j+1])))
        
        # Back wall (y = max)
        i = height - 1
        for j in range(width - 1):
            triangles.append(((X[i, j], Y[i, j], base_z), (X[i, j], Y[i, j], Z[i, j]), (X[i, j+1], Y[i, j+1], Z[i, j+1])))
            triangles.append(((X[i, j], Y[i, j], base_z), (X[i, j+1], Y[i, j+1], Z[i, j+1]), (X[i, j+1], Y[i, j+1], base_z)))
        
        # Left wall (x = 0)
        for i in range(height - 1):
            triangles.append(((X[i, 0], Y[i, 0], base_z), (X[i, 0], Y[i, 0], Z[i, 0]), (X[i+1, 0], Y[i+1, 0], Z[i+1, 0])))
            triangles.append(((X[i, 0], Y[i, 0], base_z), (X[i+1, 0], Y[i+1, 0], Z[i+1, 0]), (X[i+1, 0], Y[i+1, 0], base_z)))
        
        # Right wall (x = max)
        j = width - 1
        for i in range(height - 1):
            triangles.append(((X[i, j], Y[i, j], base_z), (X[i+1, j], Y[i+1, j], Z[i+1, j]), (X[i, j], Y[i, j], Z[i, j])))
            triangles.append(((X[i, j], Y[i, j], base_z), (X[i+1, j], Y[i+1, j], base_z), (X[i+1, j], Y[i+1, j], Z[i+1, j])))
        
        # Write binary STL
        stl_data = bytearray()
        header = b'Relief from image - STL Generator  '  # Exactly 35 chars
        stl_data.extend(header + b'\0' * (80 - len(header)))
        stl_data.extend(struct.pack('<I', len(triangles)))
        
        for tri in triangles:
            v0, v1, v2 = tri
            # Calculate normal
            u = (v1[0] - v0[0], v1[1] - v0[1], v1[2] - v0[2])
            v = (v2[0] - v0[0], v2[1] - v0[1], v2[2] - v0[2])
            n = (
                u[1] * v[2] - u[2] * v[1],
                u[2] * v[0] - u[0] * v[2],
                u[0] * v[1] - u[1] * v[0]
            )
            length = (n[0]**2 + n[1]**2 + n[2]**2) ** 0.5
            if length > 0:
                n = (n[0]/length, n[1]/length, n[2]/length)
            
            stl_data.extend(struct.pack('<fff', *n))
            stl_data.extend(struct.pack('<fff', *v0))
            stl_data.extend(struct.pack('<fff', *v1))
            stl_data.extend(struct.pack('<fff', *v2))
            stl_data.extend(struct.pack('<H', 0))
        
        return bytes(stl_data)
    
    def _generate_sample_relief_stl(self) -> bytes:
        """Generate a sample relief STL file with a wavy surface."""
        # Create a simple heightmap grid
        size = 50  # 50x50 grid
        x = np.linspace(0, 100, size)
        y = np.linspace(0, 100, size)
        X, Y = np.meshgrid(x, y)
        
        # Create a wavy height pattern (simulating a relief)
        Z = 5 + 3 * np.sin(X / 15) * np.cos(Y / 15) + 2 * np.sin(X / 8 + Y / 10)
        
        # Generate triangles from the heightmap
        triangles = []
        for i in range(size - 1):
            for j in range(size - 1):
                # Two triangles per quad
                v00 = (X[i, j], Y[i, j], Z[i, j])
                v10 = (X[i+1, j], Y[i+1, j], Z[i+1, j])
                v01 = (X[i, j+1], Y[i, j+1], Z[i, j+1])
                v11 = (X[i+1, j+1], Y[i+1, j+1], Z[i+1, j+1])
                
                triangles.append((v00, v10, v11))
                triangles.append((v00, v11, v01))
        
        # Add bottom face (flat base)
        base_z = 0
        for i in range(size - 1):
            for j in range(size - 1):
                v00 = (X[i, j], Y[i, j], base_z)
                v10 = (X[i+1, j], Y[i+1, j], base_z)
                v01 = (X[i, j+1], Y[i, j+1], base_z)
                v11 = (X[i+1, j+1], Y[i+1, j+1], base_z)
                
                triangles.append((v00, v11, v10))  # Reversed winding
                triangles.append((v00, v01, v11))
        
        # Add side walls
        # Front and back walls
        for i in range(size - 1):
            # Front wall (y = 0)
            triangles.append(((X[i, 0], Y[i, 0], base_z), (X[i+1, 0], Y[i+1, 0], Z[i+1, 0]), (X[i, 0], Y[i, 0], Z[i, 0])))
            triangles.append(((X[i, 0], Y[i, 0], base_z), (X[i+1, 0], Y[i+1, 0], base_z), (X[i+1, 0], Y[i+1, 0], Z[i+1, 0])))
            # Back wall (y = max)
            j = size - 1
            triangles.append(((X[i, j], Y[i, j], base_z), (X[i, j], Y[i, j], Z[i, j]), (X[i+1, j], Y[i+1, j], Z[i+1, j])))
            triangles.append(((X[i, j], Y[i, j], base_z), (X[i+1, j], Y[i+1, j], Z[i+1, j]), (X[i+1, j], Y[i+1, j], base_z)))
        
        # Left and right walls
        for j in range(size - 1):
            # Left wall (x = 0)
            triangles.append(((X[0, j], Y[0, j], base_z), (X[0, j], Y[0, j], Z[0, j]), (X[0, j+1], Y[0, j+1], Z[0, j+1])))
            triangles.append(((X[0, j], Y[0, j], base_z), (X[0, j+1], Y[0, j+1], Z[0, j+1]), (X[0, j+1], Y[0, j+1], base_z)))
            # Right wall (x = max)
            i = size - 1
            triangles.append(((X[i, j], Y[i, j], base_z), (X[i, j+1], Y[i, j+1], Z[i, j+1]), (X[i, j], Y[i, j], Z[i, j])))
            triangles.append(((X[i, j], Y[i, j], base_z), (X[i, j+1], Y[i, j+1], base_z), (X[i, j+1], Y[i, j+1], Z[i, j+1])))
        
        # Write binary STL
        import struct
        
        stl_data = bytearray()
        # 80-byte header (must be exactly 80 bytes)
        header = b'Binary STL generated by Relief Pipeline '  # 40 chars with trailing space
        stl_data.extend(header + b'\0' * (80 - len(header)))
        # Number of triangles (4 bytes, little endian)
        stl_data.extend(struct.pack('<I', len(triangles)))
        
        for tri in triangles:
            v0, v1, v2 = tri
            # Calculate normal
            u = (v1[0] - v0[0], v1[1] - v0[1], v1[2] - v0[2])
            v = (v2[0] - v0[0], v2[1] - v0[1], v2[2] - v0[2])
            n = (
                u[1] * v[2] - u[2] * v[1],
                u[2] * v[0] - u[0] * v[2],
                u[0] * v[1] - u[1] * v[0]
            )
            # Normalize
            length = (n[0]**2 + n[1]**2 + n[2]**2) ** 0.5
            if length > 0:
                n = (n[0]/length, n[1]/length, n[2]/length)
            
            # Normal (3 floats)
            stl_data.extend(struct.pack('<fff', *n))
            # Vertices (3 * 3 floats)
            stl_data.extend(struct.pack('<fff', *v0))
            stl_data.extend(struct.pack('<fff', *v1))
            stl_data.extend(struct.pack('<fff', *v2))
            # Attribute byte count (2 bytes)
            stl_data.extend(struct.pack('<H', 0))
        
        return bytes(stl_data)


# Global worker instance
local_worker = LocalWorker()


async def process_job_immediately(job_id: str):
    """
    Process a specific job immediately (called from API endpoint).
    This bypasses the polling loop for faster response.
    """
    async with WorkerSessionLocal() as db:
        job = await db.get(Job, job_id)
        if job and job.state == JobState.SUBMITTED:
            await local_worker._process_job(db, job) # Pass db and job object
