import json
from typing import List, Optional, Union
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    
    # Database - Use absolute path for SQLite to prevent "lost projects" on different working dirs
    DATABASE_URL: str = "sqlite+aiosqlite:///C:/Projects/3d_Printer_Converter/3dprinter-stl-creator/stl-generator/backend/app.db"
    
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
    LOCAL_STORAGE_PATH: str = "C:/Projects/3d_Printer_Converter/storage"
    
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


settings = Settings()
