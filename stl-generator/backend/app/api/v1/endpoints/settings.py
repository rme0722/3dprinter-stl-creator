"""Settings API endpoint for exposing and updating environment configuration."""
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.config import settings, _PROJECT_ROOT

router = APIRouter()


class SettingsResponse(BaseModel):
    """Current application settings."""
    # Computed paths (read-only, computed from project structure)
    database_url: str
    local_storage_path: str
    
    # Configurable tool paths (can be overridden via env vars)
    colmap_path: str
    openmvs_path: str
    
    # Status info
    colmap_available: bool
    openmvs_available: bool
    storage_exists: bool
    
    # Hints for users
    env_file_path: str
    tools_directory: str


class SettingsUpdate(BaseModel):
    """Settings that can be updated."""
    colmap_path: Optional[str] = None
    openmvs_path: Optional[str] = None
    local_storage_path: Optional[str] = None


@router.get("/settings", response_model=SettingsResponse)
async def get_settings():
    """Get current application settings and path configurations."""
    storage_path = Path(settings.LOCAL_STORAGE_PATH)
    colmap_path = Path(settings.COLMAP_PATH) if settings.COLMAP_PATH else None
    openmvs_path = Path(settings.OPENMVS_PATH) if settings.OPENMVS_PATH else None
    
    return SettingsResponse(
        database_url=settings.DATABASE_URL,
        local_storage_path=settings.LOCAL_STORAGE_PATH,
        colmap_path=settings.COLMAP_PATH or "",
        openmvs_path=settings.OPENMVS_PATH or "",
        colmap_available=colmap_path.exists() if colmap_path else False,
        openmvs_available=openmvs_path.exists() if openmvs_path else False,
        storage_exists=storage_path.exists(),
        env_file_path=str(_PROJECT_ROOT / ".env"),
        tools_directory=str(_PROJECT_ROOT / "tools"),
    )


@router.post("/settings/validate-path")
async def validate_path(path: str, path_type: str):
    """Validate that a path exists and is correct type."""
    p = Path(path)
    
    if not p.exists():
        return {"valid": False, "error": f"Path does not exist: {path}"}
    
    if path_type == "colmap":
        # COLMAP should be a .bat file
        if not path.endswith(".bat") and not path.endswith("colmap"):
            return {"valid": False, "error": "COLMAP path should point to COLMAP.bat"}
    elif path_type == "openmvs":
        # OpenMVS should be a directory containing executables
        if not p.is_dir():
            return {"valid": False, "error": "OpenMVS path should be a directory"}
        if not (p / "InterfaceCOLMAP.exe").exists() and not (p / "InterfaceCOLMAP").exists():
            return {"valid": False, "error": "OpenMVS directory should contain InterfaceCOLMAP"}
    elif path_type == "storage":
        if not p.is_dir():
            return {"valid": False, "error": "Storage path should be a directory"}
    
    return {"valid": True}


@router.get("/settings/env-template")
async def get_env_template():
    """Get a template .env file for customizing settings."""
    template = f"""# STL Creator Environment Configuration
# Copy this file to .env and modify as needed

# Database (SQLite path, relative paths work)
# DATABASE_URL=sqlite+aiosqlite:///path/to/app.db

# Storage directory for uploads and outputs
# LOCAL_STORAGE_PATH={settings.LOCAL_STORAGE_PATH}

# Tool paths (optional - will auto-detect if in PATH or tools/ folder)
# COLMAP_PATH={settings.COLMAP_PATH or "C:/Path/To/COLMAP/COLMAP.bat"}
# OPENMVS_PATH={settings.OPENMVS_PATH or "C:/Path/To/OpenMVS"}
"""
    return {"template": template}
