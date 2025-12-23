from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid
import logging

from app.db.database import get_db
from app.models import Project
from app.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project: ProjectCreate,
    db: AsyncSession = Depends(get_db)
) -> Project:
    """Create a new project"""
    logger.info(f"=== CREATE PROJECT ENDPOINT ===")
    logger.info(f"Project data: {project}")
    
    logger.info("Creating project object...")
    db_project = Project(
        id=f"proj_{uuid.uuid4().hex[:12]}",
        user_id="user_demo",  # TODO: Get from auth
        name=project.name,
        description=project.description
    )
    logger.info(f"Project object created with ID: {db_project.id}")
    
    logger.info("Adding project to database...")
    db.add(db_project)
    
    logger.info("Committing to database...")
    await db.commit()
    
    logger.info("Refreshing project object...")
    await db.refresh(db_project)
    
    logger.info("Project creation completed successfully")
    return db_project


@router.get("/", response_model=List[ProjectResponse])
@router.get("", response_model=List[ProjectResponse])
async def list_projects(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
) -> List[Project]:
    """List all projects for the current user"""
    result = await db.execute(
        select(Project)
        .where(Project.user_id == "user_demo")  # TODO: Get from auth
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    db: AsyncSession = Depends(get_db)
) -> Project:
    """Get a specific project by ID"""
    result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    return project


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    project_update: ProjectUpdate,
    db: AsyncSession = Depends(get_db)
) -> Project:
    """Update a project"""
    result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    update_data = project_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)
    
    await db.commit()
    await db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: str,
    db: AsyncSession = Depends(get_db)
) -> None:
    """Delete a project"""
    result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    await db.delete(project)
    await db.commit()
