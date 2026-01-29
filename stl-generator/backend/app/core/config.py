import json
import os
from pathlib import Path
from typing import List, Optional, Union
from pydantic import AnyHttpUrl, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# Compute paths relative to this file's location
_THIS_FILE = Path(__file__).resolve()
_BACKEND_DIR = _THIS_FILE.parent.parent.parent  # backend/
_PROJECT_ROOT = _BACKEND_DIR.parent.parent  # 3dprinter-stl-creator/


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")
    
    PROJECT_NAME: str = "3D STL Generator"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    BASE_URL: str = "http://localhost:8000"
    
    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days
    
    # Database - computed relative to backend dir, overridable via DATABASE_URL env var
    DATABASE_URL: str = ""
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"
    
    # S3 Storage
    S3_ENDPOINT_URL: str = "http://localhost:9000"
    S3_ACCESS_KEY_ID: str = "minioadmin"
    S3_SECRET_ACCESS_KEY: str = "minioadmin"
    S3_BUCKET_NAME: str = "stl-generator"
    
    # CORS - default includes localhost for development
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000"]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        if isinstance(v, str):
            if v.startswith("["):
                return json.loads(v)
            return [i.strip() for i in v.split(",") if i.strip()]
        if isinstance(v, list):
            return v
        raise ValueError(v)
    
    # Job Processing
    MAX_UPLOAD_SIZE_MB: int = 100
    MAX_PHOTOS_PER_JOB: int = 200
    MIN_PHOTOS_FOR_SCAN: int = 30
    MAX_RETAINED_JOBS: int = 10
    MAX_RETAINED_PROJECTS: int = 3
    
    # Storage path - computed relative to project root, overridable via LOCAL_STORAGE_PATH env var
    LOCAL_STORAGE_PATH: str = ""
    
    # Tool paths - overridable via env vars COLMAP_PATH and OPENMVS_PATH
    COLMAP_PATH: str = ""
    OPENMVS_PATH: str = ""
    
    # Quality Thresholds
    QUALITY_SCORE_GREAT: float = 0.80
    QUALITY_SCORE_GOOD: float = 0.60
    QUALITY_SCORE_RISKY: float = 0.40
    
    # Pipeline Weights
    SCAN_WEIGHT_INPUT: float = 0.35
    SCAN_WEIGHT_RECON: float = 0.45
    SCAN_WEIGHT_PRINT: float = 0.20
    
    RELIEF_WEIGHT_INPUT: float = 0.50
    RELIEF_WEIGHT_RECON: float = 0.20
    RELIEF_WEIGHT_PRINT: float = 0.30
    
    GEN_WEIGHT_INPUT: float = 0.20
    GEN_WEIGHT_RECON: float = 0.50
    GEN_WEIGHT_PRINT: float = 0.30

    @model_validator(mode="after")
    def compute_dynamic_paths(self) -> "Settings":
        """Compute paths relative to project structure if not set via env vars."""
        # Database URL - relative to backend directory
        if not self.DATABASE_URL:
            db_path = _BACKEND_DIR / "app.db"
            self.DATABASE_URL = f"sqlite+aiosqlite:///{db_path.as_posix()}"
        
        # Storage path - relative to project root (3dprinter-stl-creator/storage)
        if not self.LOCAL_STORAGE_PATH:
            self.LOCAL_STORAGE_PATH = str(_PROJECT_ROOT / "storage")
        
        # Tool paths - check local tools/ folder, then common install locations
        if not self.COLMAP_PATH:
            local_colmap = _PROJECT_ROOT / "tools" / "COLMAP"
            system_colmap = Path(r"C:\Tools\COLMAP")
            if local_colmap.exists():
                # Find COLMAP.bat in subdirectory
                for bat in local_colmap.rglob("COLMAP.bat"):
                    self.COLMAP_PATH = str(bat)
                    break
            elif system_colmap.exists():
                for bat in system_colmap.rglob("COLMAP.bat"):
                    self.COLMAP_PATH = str(bat)
                    break
        
        if not self.OPENMVS_PATH:
            local_openmvs = _PROJECT_ROOT / "tools" / "OpenMVS"
            system_openmvs = Path(r"C:\Tools\OpenMVS")
            if local_openmvs.exists():
                self.OPENMVS_PATH = str(local_openmvs)
            elif system_openmvs.exists():
                self.OPENMVS_PATH = str(system_openmvs)
        
        return self


settings = Settings()

