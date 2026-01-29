#!/usr/bin/env python3
"""
Detached COLMAP Pipeline Runner

This script runs as a completely independent process that survives server restarts.
It writes progress and status to a JSON file that the backend can monitor.

Usage:
    python run_colmap_detached.py <job_id> <image_dir> <workspace_dir>
"""

import sys
import os
import json
import subprocess
import time
import shutil
from pathlib import Path
from datetime import datetime


def get_colmap_path() -> Path:
    """Get COLMAP path from env var, config, local tools, or system PATH."""
    # 1. Environment variable
    if env := os.environ.get("COLMAP_PATH"):
        return Path(env)
    
    # 2. Try importing from config (may fail if running standalone)
    try:
        # Add parent dirs to path for standalone execution
        script_dir = Path(__file__).parent
        backend_dir = script_dir.parent.parent
        sys.path.insert(0, str(backend_dir))
        from app.core.config import settings
        if settings.COLMAP_PATH:
            return Path(settings.COLMAP_PATH)
    except Exception:
        pass
    
    # 3. Local tools folder
    project_root = Path(__file__).parents[4]
    local_colmap = project_root / "tools" / "COLMAP"
    if local_colmap.exists():
        for bat in local_colmap.rglob("COLMAP.bat"):
            return bat
    
    # 4. System install location
    system_colmap = Path(r"C:\Tools\COLMAP")
    if system_colmap.exists():
        for bat in system_colmap.rglob("COLMAP.bat"):
            return bat
    
    # 5. System PATH
    if which := shutil.which("colmap"):
        return Path(which)
    
    raise RuntimeError("COLMAP not found. Set COLMAP_PATH environment variable or install COLMAP.")


def get_openmvs_path() -> Path:
    """Get OpenMVS path from env var, config, local tools, or system PATH."""
    # 1. Environment variable
    if env := os.environ.get("OPENMVS_PATH"):
        return Path(env)
    
    # 2. Try importing from config
    try:
        script_dir = Path(__file__).parent
        backend_dir = script_dir.parent.parent
        sys.path.insert(0, str(backend_dir))
        from app.core.config import settings
        if settings.OPENMVS_PATH:
            return Path(settings.OPENMVS_PATH)
    except Exception:
        pass
    
    # 3. Local tools folder
    project_root = Path(__file__).parents[4]
    local_openmvs = project_root / "tools" / "OpenMVS"
    if local_openmvs.exists():
        return local_openmvs
    
    # 4. System install location
    system_openmvs = Path(r"C:\Tools\OpenMVS")
    if system_openmvs.exists():
        return system_openmvs
    
    # 5. System PATH - check for InterfaceCOLMAP
    if which := shutil.which("InterfaceCOLMAP"):
        return Path(which).parent
    
    raise RuntimeError("OpenMVS not found. Set OPENMVS_PATH environment variable or install OpenMVS.")


# Lazy-loaded paths (computed on first use)
_COLMAP_PATH = None
_OPENMVS_PATH = None

def COLMAP_PATH() -> Path:
    global _COLMAP_PATH
    if _COLMAP_PATH is None:
        _COLMAP_PATH = get_colmap_path()
    return _COLMAP_PATH

def OPENMVS_PATH() -> Path:
    global _OPENMVS_PATH
    if _OPENMVS_PATH is None:
        _OPENMVS_PATH = get_openmvs_path()
    return _OPENMVS_PATH




def write_status(workspace_dir: Path, status_data: dict):
    """Write status to JSON file atomically."""
    status_file = workspace_dir / "status.json"
    temp_file = workspace_dir / "status.json.tmp"
    
    status_data["updated_at"] = datetime.now().isoformat()
    
    with open(temp_file, 'w') as f:
        json.dump(status_data, f, indent=2)
    
    # Atomic rename
    temp_file.replace(status_file)


def run_colmap_command(command: str, args: list, workspace_dir: Path, status: dict) -> bool:
    """Run a COLMAP command and return success status."""
    cmd = [str(COLMAP_PATH()), command] + [str(a) for a in args]
    print(f"[COLMAP] Running: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            shell=True
        )
        
        if result.returncode != 0:
            error_msg = result.stderr or result.stdout
            print(f"[COLMAP] {command} FAILED: {error_msg[:500]}")
            status["error"] = f"{command} failed: {error_msg[:500]}"
            return False
        
        print(f"[COLMAP] {command} completed successfully")
        return True
    except Exception as e:
        print(f"[COLMAP] {command} EXCEPTION: {e}")
        status["error"] = str(e)
        return False


def run_openmvs_command(executable: str, args: list, mvs_dir: Path, status: dict) -> bool:
    """Run an OpenMVS command."""
    exe_path = OPENMVS_PATH() / f"{executable}.exe"
    cmd = [str(exe_path)] + [str(a) for a in args]
    print(f"[OpenMVS] Running: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(mvs_dir)
        )
        
        if result.returncode != 0:
            error_msg = result.stderr or result.stdout
            print(f"[OpenMVS] {executable} FAILED: {error_msg[:500]}")
            status["error"] = f"{executable} failed: {error_msg[:500]}"
            return False
        
        print(f"[OpenMVS] {executable} completed successfully")
        return True
    except Exception as e:
        print(f"[OpenMVS] {executable} EXCEPTION: {e}")
        status["error"] = str(e)
        return False


def run_pipeline(job_id: str, image_dir: Path, workspace_dir: Path):
    """Run the complete COLMAP + OpenMVS pipeline."""
    
    # Initialize status
    status = {
        "job_id": job_id,
        "stage": "initializing",
        "progress": 0,
        "status": "running",
        "output_mesh": None,
        "error": None,
        "started_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }
    
    # Create directories
    database_path = workspace_dir / "database.db"
    sparse_dir = workspace_dir / "sparse"
    dense_dir = workspace_dir / "dense"
    mvs_dir = workspace_dir / "mvs"
    
    for d in [sparse_dir, dense_dir, mvs_dir]:
        d.mkdir(parents=True, exist_ok=True)
    
    write_status(workspace_dir, status)
    
    try:
        # Stage 1: Feature Extraction (10%)
        status["stage"] = "feature_extraction"
        status["progress"] = 5
        write_status(workspace_dir, status)
        
        if not run_colmap_command("feature_extractor", [
            "--image_path", str(image_dir),
            "--database_path", str(database_path),
            "--ImageReader.single_camera", "1",
            "--SiftExtraction.use_gpu", "0"
        ], workspace_dir, status):
            status["status"] = "failed"
            write_status(workspace_dir, status)
            return
        
        status["progress"] = 10
        write_status(workspace_dir, status)
        
        # Stage 2: Exhaustive Matching (20%)
        status["stage"] = "matching"
        status["progress"] = 15
        write_status(workspace_dir, status)
        
        if not run_colmap_command("exhaustive_matcher", [
            "--database_path", str(database_path),
            "--SiftMatching.use_gpu", "0"
        ], workspace_dir, status):
            status["status"] = "failed"
            write_status(workspace_dir, status)
            return
        
        status["progress"] = 20
        write_status(workspace_dir, status)
        
        # Stage 3: Sparse Reconstruction (30%)
        status["stage"] = "sparse_reconstruction"
        status["progress"] = 25
        write_status(workspace_dir, status)
        
        if not run_colmap_command("mapper", [
            "--image_path", str(image_dir),
            "--database_path", str(database_path),
            "--output_path", str(sparse_dir)
        ], workspace_dir, status):
            status["status"] = "failed"
            write_status(workspace_dir, status)
            return
        
        status["progress"] = 30
        write_status(workspace_dir, status)
        
        # Find sparse model
        sparse_model_dir = sparse_dir / "0"
        if not sparse_model_dir.exists():
            model_dirs = list(sparse_dir.iterdir())
            if model_dirs:
                sparse_model_dir = model_dirs[0]
            else:
                status["error"] = "No sparse model found"
                status["status"] = "failed"
                write_status(workspace_dir, status)
                return
        
        # Stage 4: Image Undistortion (40%)
        status["stage"] = "undistortion"
        status["progress"] = 35
        write_status(workspace_dir, status)
        
        if not run_colmap_command("image_undistorter", [
            "--image_path", str(image_dir),
            "--input_path", str(sparse_model_dir),
            "--output_path", str(dense_dir),
            "--output_type", "COLMAP"
        ], workspace_dir, status):
            status["status"] = "failed"
            write_status(workspace_dir, status)
            return
        
        status["progress"] = 40
        write_status(workspace_dir, status)
        
        # Stage 5: Dense Stereo (60%) - with granular progress tracking
        status["stage"] = "patch_match_stereo"
        status["progress"] = 45
        write_status(workspace_dir, status)
        
        # Count images to estimate expected depth maps (2x for geom_consistency)
        num_images = len(list(image_dir.glob("*.[jJ][pP][gG]"))) + len(list(image_dir.glob("*.[pP][nN][gG]")))
        expected_depth_maps = num_images * 2  # photometric + geometric passes
        
        depth_maps_dir = dense_dir / "stereo" / "depth_maps"
        
        # Run patch_match_stereo in a thread while monitoring progress
        import threading
        import time
        
        patch_match_result = {"success": False, "error": None}
        
        def run_patch_match():
            colmap_exe = COLMAP_PATH()  # Get path before entering thread
            cmd = [str(colmap_exe), "patch_match_stereo",
                   "--workspace_path", str(dense_dir),
                   "--PatchMatchStereo.geom_consistency", "true"]
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
                if result.returncode != 0:
                    patch_match_result["error"] = result.stderr or result.stdout
                else:
                    patch_match_result["success"] = True
            except Exception as e:
                patch_match_result["error"] = str(e)
        
        # Start patch_match in thread
        patch_thread = threading.Thread(target=run_patch_match)
        patch_thread.start()
        
        # Monitor progress while thread runs
        while patch_thread.is_alive():
            # Count generated depth maps
            if depth_maps_dir.exists():
                depth_map_count = len(list(depth_maps_dir.glob("*.bin")))
                # Progress from 45% to 60% during this stage
                stage_progress = min(depth_map_count / max(expected_depth_maps, 1), 1.0)
                status["progress"] = 45 + int(stage_progress * 15)
                status["detail"] = f"Depth maps: {depth_map_count}/{expected_depth_maps}"
                write_status(workspace_dir, status)
            
            time.sleep(5)  # Update every 5 seconds
        
        patch_thread.join()
        
        if not patch_match_result["success"]:
            status["error"] = f"patch_match_stereo failed: {patch_match_result['error'][:500] if patch_match_result['error'] else 'Unknown error'}"
            status["status"] = "failed"
            write_status(workspace_dir, status)
            return
        
        status["progress"] = 60
        status["detail"] = None
        write_status(workspace_dir, status)
        
        # Stage 6: Stereo Fusion (70%)
        status["stage"] = "fusion"
        status["progress"] = 65
        write_status(workspace_dir, status)
        
        fused_ply = dense_dir / "fused.ply"
        if not run_colmap_command("stereo_fusion", [
            "--workspace_path", str(dense_dir),
            "--output_path", str(fused_ply)
        ], workspace_dir, status):
            status["status"] = "failed"
            write_status(workspace_dir, status)
            return
        
        status["progress"] = 70
        write_status(workspace_dir, status)
        
        # Stage 7: Mesh Reconstruction (85%)
        status["stage"] = "meshing"
        status["progress"] = 75
        write_status(workspace_dir, status)
        
        # Try OpenMVS first, fall back to COLMAP Poisson
        scene_mvs = mvs_dir / "scene.mvs"
        mesh_ply = None
        
        if run_openmvs_command("InterfaceCOLMAP", [
            "--working-folder", str(dense_dir),
            "--input-file", str(dense_dir),
            "--output-file", str(scene_mvs)
        ], mvs_dir, status):
            # Run ReconstructMesh
            mesh_mvs = mvs_dir / "scene_mesh.mvs"
            if run_openmvs_command("ReconstructMesh", [
                "--input-file", str(scene_mvs),
                "--output-file", str(mesh_mvs)
            ], mvs_dir, status):
                mesh_ply = mvs_dir / "scene_mesh.ply"
        
        # Fallback to COLMAP Poisson
        if mesh_ply is None or not mesh_ply.exists():
            print("[COLMAP] OpenMVS failed, using COLMAP Poisson mesher")
            mesh_ply = dense_dir / "meshed.ply"
            if not run_colmap_command("poisson_mesher", [
                "--input_path", str(fused_ply),
                "--output_path", str(mesh_ply)
            ], workspace_dir, status):
                status["status"] = "failed"
                write_status(workspace_dir, status)
                return
        
        status["progress"] = 90
        write_status(workspace_dir, status)
        
        # Success!
        if mesh_ply and mesh_ply.exists():
            status["stage"] = "completed"
            status["progress"] = 100
            status["status"] = "completed"
            status["output_mesh"] = str(mesh_ply)
            write_status(workspace_dir, status)
            print(f"[SUCCESS] Pipeline completed! Mesh: {mesh_ply}")
        else:
            status["error"] = "No mesh file generated"
            status["status"] = "failed"
            write_status(workspace_dir, status)
            
    except Exception as e:
        import traceback
        status["error"] = str(e)
        status["status"] = "failed"
        print(f"[ERROR] Pipeline failed: {e}")
        print(traceback.format_exc())
        write_status(workspace_dir, status)


def main():
    if len(sys.argv) != 4:
        print(f"Usage: {sys.argv[0]} <job_id> <image_dir> <workspace_dir>")
        sys.exit(1)
    
    job_id = sys.argv[1]
    image_dir = Path(sys.argv[2])
    workspace_dir = Path(sys.argv[3])
    
    print(f"[DETACHED] Starting COLMAP pipeline for job {job_id}")
    print(f"  Image dir: {image_dir}")
    print(f"  Workspace: {workspace_dir}")
    
    run_pipeline(job_id, image_dir, workspace_dir)


if __name__ == "__main__":
    main()
