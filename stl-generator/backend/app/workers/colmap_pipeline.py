"""COLMAP + OpenMVS Pipeline Wrapper

This module wraps the COLMAP and OpenMVS CLI tools to provide
a high-quality dense MVS photogrammetry pipeline.
"""

import os
import asyncio
import logging
import subprocess
from pathlib import Path
from typing import Optional, Callable, Awaitable
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PipelineProgress:
    """Progress update for the pipeline."""
    stage: str
    percentage: int
    message: str


# Tool paths - configured for development machine
COLMAP_PATH = Path(r"C:\Tools\COLMAP\COLMAP-3.9.1-windows-cuda\COLMAP.bat")
OPENMVS_PATH = Path(r"C:\Tools\OpenMVS")


class ColmapMVSPipeline:
    """
    COLMAP + OpenMVS dense reconstruction pipeline.
    
    Pipeline stages:
    1. Feature extraction (COLMAP)
    2. Exhaustive matching (COLMAP)
    3. Sparse reconstruction / Mapper (COLMAP)
    4. Image undistortion (COLMAP)
    5. Dense stereo (COLMAP patch_match_stereo)
    6. Stereo fusion (COLMAP)
    7. Mesh reconstruction (OpenMVS)
    8. Mesh refinement (OpenMVS)
    """
    
    def __init__(
        self,
        image_dir: Path,
        workspace_dir: Path,
        progress_callback: Optional[Callable[[PipelineProgress], Awaitable[None]]] = None
    ):
        self.image_dir = Path(image_dir)
        self.workspace_dir = Path(workspace_dir)
        self.progress_callback = progress_callback
        
        # Create workspace subdirectories
        self.database_path = self.workspace_dir / "database.db"
        self.sparse_dir = self.workspace_dir / "sparse"
        self.dense_dir = self.workspace_dir / "dense"
        self.mvs_dir = self.workspace_dir / "mvs"
        
        for d in [self.sparse_dir, self.dense_dir, self.mvs_dir]:
            d.mkdir(parents=True, exist_ok=True)
    
    async def _report_progress(self, stage: str, percentage: int, message: str):
        """Report progress to callback if available."""
        if self.progress_callback:
            await self.progress_callback(PipelineProgress(stage, percentage, message))
        logger.info(f"[{percentage}%] {stage}: {message}")
    
    async def _run_colmap(self, command: str, args: list[str]) -> bool:
        """Run a COLMAP command."""
        cmd = [str(COLMAP_PATH), command] + args
        logger.debug(f"Running COLMAP: {' '.join(cmd)}")
        
        try:
            # Run in separate thread to not block async loop
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                logger.error(f"COLMAP {command} failed: {stderr.decode()}")
                return False
            
            logger.debug(f"COLMAP {command} output: {stdout.decode()[:500]}")
            return True
        except Exception as e:
            logger.error(f"COLMAP {command} exception: {e}")
            return False
    
    async def _run_openmvs(self, executable: str, args: list[str]) -> bool:
        """Run an OpenMVS executable."""
        exe_path = OPENMVS_PATH / f"{executable}.exe"
        cmd = [str(exe_path)] + args
        logger.debug(f"Running OpenMVS: {' '.join(cmd)}")
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.mvs_dir)
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                logger.error(f"OpenMVS {executable} failed: {stderr.decode()}")
                return False
            
            logger.debug(f"OpenMVS {executable} output: {stdout.decode()[:500]}")
            return True
        except Exception as e:
            logger.error(f"OpenMVS {executable} exception: {e}")
            return False

    async def run_full_pipeline(self) -> Optional[Path]:
        """
        Run the complete dense MVS reconstruction pipeline.
        
        Returns:
            Path to the final mesh file, or None if failed.
        """
        # Stage 1: Feature Extraction (10%)
        await self._report_progress("Feature Extraction", 5, "Extracting SIFT features from images...")
        success = await self._run_colmap("feature_extractor", [
            "--image_path", str(self.image_dir),
            "--database_path", str(self.database_path),
            "--ImageReader.single_camera", "1",
            "--SiftExtraction.use_gpu", "0"  # Use CPU - more reliable
        ])
        if not success:
            return None
        await self._report_progress("Feature Extraction", 10, "Features extracted successfully.")
        
        # Stage 2: Exhaustive Matching (20%)
        await self._report_progress("Matching", 15, "Matching features between images...")
        success = await self._run_colmap("exhaustive_matcher", [
            "--database_path", str(self.database_path),
            "--SiftMatching.use_gpu", "0"  # Use CPU - more reliable
        ])
        if not success:
            return None
        await self._report_progress("Matching", 20, "Feature matching complete.")
        
        # Stage 3: Sparse Reconstruction (30%)
        await self._report_progress("Sparse Reconstruction", 25, "Building sparse 3D model...")
        success = await self._run_colmap("mapper", [
            "--image_path", str(self.image_dir),
            "--database_path", str(self.database_path),
            "--output_path", str(self.sparse_dir)
        ])
        if not success:
            return None
        await self._report_progress("Sparse Reconstruction", 30, "Sparse reconstruction complete.")
        
        # Find the sparse model (usually in sparse/0/)
        sparse_model_dir = self.sparse_dir / "0"
        if not sparse_model_dir.exists():
            # Try to find any model directory
            model_dirs = list(self.sparse_dir.iterdir())
            if model_dirs:
                sparse_model_dir = model_dirs[0]
            else:
                logger.error("No sparse model found!")
                return None
        
        # Stage 4: Image Undistortion (40%)
        await self._report_progress("Undistortion", 35, "Undistorting images for MVS...")
        success = await self._run_colmap("image_undistorter", [
            "--image_path", str(self.image_dir),
            "--input_path", str(sparse_model_dir),
            "--output_path", str(self.dense_dir),
            "--output_type", "COLMAP"
        ])
        if not success:
            return None
        await self._report_progress("Undistortion", 40, "Image undistortion complete.")
        
        # Stage 5: Dense Stereo (60%)
        await self._report_progress("Dense Stereo", 45, "Computing dense depth maps (this is slow)...")
        success = await self._run_colmap("patch_match_stereo", [
            "--workspace_path", str(self.dense_dir),
            "--PatchMatchStereo.geom_consistency", "true"
        ])
        if not success:
            return None
        await self._report_progress("Dense Stereo", 60, "Dense stereo complete.")
        
        # Stage 6: Stereo Fusion (70%)
        await self._report_progress("Fusion", 65, "Fusing depth maps into point cloud...")
        fused_ply = self.dense_dir / "fused.ply"
        success = await self._run_colmap("stereo_fusion", [
            "--workspace_path", str(self.dense_dir),
            "--output_path", str(fused_ply)
        ])
        if not success:
            return None
        await self._report_progress("Fusion", 70, f"Point cloud saved to {fused_ply.name}")
        
        # Stage 7: Mesh Reconstruction with OpenMVS (85%)
        await self._report_progress("Meshing", 75, "Reconstructing mesh from point cloud...")
        
        # First, convert COLMAP output to OpenMVS format using InterfaceCOLMAP
        scene_mvs = self.mvs_dir / "scene.mvs"
        success = await self._run_openmvs("InterfaceCOLMAP", [
            "--working-folder", str(self.dense_dir),
            "--input-file", str(self.dense_dir),
            "--output-file", str(scene_mvs)
        ])
        if not success:
            # Fallback: try using the fused PLY directly with Poisson
            logger.warning("InterfaceCOLMAP failed, falling back to COLMAP Poisson meshing")
            mesh_ply = self.dense_dir / "meshed.ply"
            success = await self._run_colmap("poisson_mesher", [
                "--input_path", str(fused_ply),
                "--output_path", str(mesh_ply)
            ])
            if success:
                await self._report_progress("Meshing", 90, "Mesh created via COLMAP Poisson")
                return mesh_ply
            return None
        
        # Run ReconstructMesh
        mesh_mvs = self.mvs_dir / "scene_mesh.mvs"
        success = await self._run_openmvs("ReconstructMesh", [
            "--input-file", str(scene_mvs),
            "--output-file", str(mesh_mvs)
        ])
        if not success:
            return None
        await self._report_progress("Meshing", 85, "Initial mesh reconstructed.")
        
        # Stage 8: Mesh Refinement (95%)
        await self._report_progress("Refinement", 90, "Refining mesh surface...")
        refined_mvs = self.mvs_dir / "scene_mesh_refine.mvs"
        success = await self._run_openmvs("RefineMesh", [
            "--input-file", str(mesh_mvs),
            "--output-file", str(refined_mvs),
            "--scales", "2"
        ])
        if not success:
            # Use unrefined mesh if refinement fails
            refined_mvs = mesh_mvs
        
        await self._report_progress("Complete", 100, "Dense reconstruction complete!")
        
        # The mesh is saved alongside the .mvs file as a .ply
        mesh_ply = self.mvs_dir / "scene_mesh_refine.ply"
        if not mesh_ply.exists():
            mesh_ply = self.mvs_dir / "scene_mesh.ply"
        
        return mesh_ply if mesh_ply.exists() else None


async def run_colmap_pipeline(
    image_dir: Path,
    workspace_dir: Path,
    progress_callback: Optional[Callable[[PipelineProgress], Awaitable[None]]] = None
) -> Optional[Path]:
    """
    Convenience function to run the full COLMAP+OpenMVS pipeline.
    
    Args:
        image_dir: Directory containing input images
        workspace_dir: Working directory for intermediate files
        progress_callback: Optional async callback for progress updates
    
    Returns:
        Path to the final mesh PLY file, or None if failed
    """
    pipeline = ColmapMVSPipeline(image_dir, workspace_dir, progress_callback)
    return await pipeline.run_full_pipeline()
