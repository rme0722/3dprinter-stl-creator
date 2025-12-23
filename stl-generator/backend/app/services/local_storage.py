"""
Local file storage service for development/single-user deployment.
Stores files on the local filesystem instead of S3.
"""

import os
import hashlib
import aiofiles
from pathlib import Path
from typing import Optional

from app.core.config import settings

# Base directory for local file storage
STORAGE_BASE = Path(settings.LOCAL_STORAGE_PATH if hasattr(settings, 'LOCAL_STORAGE_PATH') 
                    else "./storage")


def get_storage_path(category: str, job_id: str, filename: str) -> Path:
    """Get the full path for storing a file."""
    path = STORAGE_BASE / category / job_id
    path.mkdir(parents=True, exist_ok=True)
    return path / filename


def get_relative_uri(category: str, job_id: str, filename: str) -> str:
    """Get the relative URI for a stored file."""
    return f"local://{category}/{job_id}/{filename}"


async def save_file(
    content: bytes,
    category: str,
    job_id: str,
    filename: str
) -> tuple[str, str, int]:
    """
    Save a file to local storage.
    
    Returns:
        tuple: (uri, sha256_hash, size_bytes)
    """
    path = get_storage_path(category, job_id, filename)
    
    # Calculate hash
    sha256_hash = hashlib.sha256(content).hexdigest()
    
    # Save file
    async with aiofiles.open(path, 'wb') as f:
        await f.write(content)
    
    uri = get_relative_uri(category, job_id, filename)
    return uri, sha256_hash, len(content)


async def read_file(uri: str) -> Optional[bytes]:
    """
    Read a file from local storage.
    
    Args:
        uri: The local:// URI of the file
        
    Returns:
        File contents as bytes, or None if not found
    """
    if not uri.startswith("local://"):
        return None
    
    relative_path = uri.replace("local://", "")
    path = STORAGE_BASE / relative_path
    
    if not path.exists():
        return None
    
    async with aiofiles.open(path, 'rb') as f:
        return await f.read()


def get_file_path(uri: str) -> Optional[Path]:
    """Convert a local:// URI to an absolute file path.
    
    Returns None if the URI is invalid or the file doesn't exist.
    """
    if not uri.startswith("local://"):
        return None
    rel_path = uri[8:]  # Remove 'local://' prefix
    file_path = STORAGE_BASE / rel_path
    if not file_path.exists():
        print(f"Warning: Storage file not found: {file_path}")
        return None
    return file_path


def delete_file(uri: str) -> bool:
    """
    Delete a file from local storage.
    
    Returns:
        True if deleted, False if not found
    """
    path = get_file_path(uri)
    if path and path.exists():
        path.unlink()
        return True
    return False


# Ensure storage directory exists on import
STORAGE_BASE.mkdir(parents=True, exist_ok=True)
