"""Test script for COLMAP + OpenMVS pipeline."""
import asyncio
import logging
from pathlib import Path

# Add parent to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent))

from app.workers.colmap_pipeline import run_colmap_pipeline, PipelineProgress

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


async def progress_handler(progress: PipelineProgress):
    """Print progress updates."""
    print(f"[{progress.percentage:3d}%] {progress.stage}: {progress.message}")


async def main():
    # Use Sceaux Castle benchmark (validation_photos is at stl-generator level, not backend)
    image_dir = Path(__file__).parent.parent / "validation_photos" / "sceaux_castle"
    workspace_dir = Path(__file__).parent / "test_colmap_output"
    
    if not image_dir.exists():
        print(f"ERROR: Image directory not found: {image_dir}")
        print("Please run download_benchmark.py first.")
        return
    
    workspace_dir.mkdir(exist_ok=True)
    
    print(f"Running COLMAP+OpenMVS pipeline on: {image_dir}")
    print(f"Output directory: {workspace_dir}")
    print("-" * 60)
    
    result = await run_colmap_pipeline(
        image_dir=image_dir,
        workspace_dir=workspace_dir,
        progress_callback=progress_handler
    )
    
    if result:
        print("-" * 60)
        print(f"SUCCESS! Final mesh saved to: {result}")
        print(f"File size: {result.stat().st_size / 1024 / 1024:.2f} MB")
    else:
        print("-" * 60)
        print("FAILED: Pipeline did not complete successfully.")


if __name__ == "__main__":
    asyncio.run(main())
