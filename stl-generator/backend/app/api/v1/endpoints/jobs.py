from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

from app.db.database import get_db
from app.models import Job, Project, PrinterProfile
from app.models.job import JobState, PipelineType
from app.schemas.job import JobCreate, JobResponse, JobUpdate, JobSubmit

router = APIRouter()


@router.post("/projects/{project_id}/jobs", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    project_id: str,
    job: JobCreate,
    db: AsyncSession = Depends(get_db)
) -> Job:
    """Create a new job in DRAFT state"""
    # Verify project exists
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Verify printer profile exists
    printer_profile = await db.get(PrinterProfile, job.printer_profile_id)
    if not printer_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Printer profile not found"
        )
    
    db_job = Job(
        id=f"job_{uuid.uuid4().hex[:12]}",
        project_id=project_id,
        pipeline_type=job.pipeline_type,
        printer_profile_id=job.printer_profile_id,
        model_preset_id=job.model_preset_id,
        config=job.config or {},
        state=JobState.DRAFT
    )
    db.add(db_job)
    await db.commit()
    await db.refresh(db_job)
    return db_job


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    db: AsyncSession = Depends(get_db)
) -> Job:
    """Get a specific job by ID"""
    job = await db.get(Job, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    return job


@router.patch("/jobs/{job_id}", response_model=JobResponse)
async def update_job(
    job_id: str,
    job_update: JobUpdate,
    db: AsyncSession = Depends(get_db)
) -> Job:
    """Update a job (only allowed in DRAFT state or specific fields)"""
    job = await db.get(Job, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    # Only allow full updates in DRAFT state
    if job.state != JobState.DRAFT and job_update.config is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only update config in DRAFT state"
        )
    
    update_data = job_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(job, field, value)
    
    await db.commit()
    await db.refresh(job)
    return job


@router.post("/jobs/{job_id}/submit", response_model=JobResponse)
async def submit_job(
    job_id: str,
    db: AsyncSession = Depends(get_db)
) -> Job:
    """Submit a job for processing"""
    job = await db.get(Job, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    if not job.can_transition_to(JobState.SUBMITTED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot submit job in state {job.state}"
        )
    
    job.state = JobState.SUBMITTED
    job.submitted_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(job)
    
    # TODO: Trigger async processing
    
    return job


@router.post("/jobs/{job_id}/cancel", response_model=JobResponse)
async def cancel_job(
    job_id: str,
    db: AsyncSession = Depends(get_db)
) -> Job:
    """Cancel a job"""
    job = await db.get(Job, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    if not job.can_transition_to(JobState.CANCELLED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel job in state {job.state}"
        )
    
    job.state = JobState.CANCELLED
    
    await db.commit()
    await db.refresh(job)
    return job


@router.post("/jobs/{job_id}/resume", response_model=JobResponse)
async def resume_job(
    job_id: str,
    action_data: Optional[dict] = None,
    db: AsyncSession = Depends(get_db)
) -> Job:
    """Resume a job from ACTION_REQUIRED or REVIEW_REQUIRED state"""
    job = await db.get(Job, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    if job.state == JobState.ACTION_REQUIRED:
        # Process action data and transition to VALIDATING
        job.state = JobState.VALIDATING
        job.hold_reason = None
    elif job.state == JobState.REVIEW_REQUIRED:
        # User accepted preview, continue processing
        job.state = JobState.RUNNING
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot resume job in state {job.state}"
        )
    
    await db.commit()
    await db.refresh(job)
    
    # TODO: Trigger async processing continuation
    
    return job


@router.get("/projects/{project_id}/jobs", response_model=List[JobResponse])
async def list_project_jobs(
    project_id: str,
    skip: int = 0,
    limit: int = 100,
    state: Optional[JobState] = None,
    db: AsyncSession = Depends(get_db)
) -> List[Job]:
    """List all jobs for a project"""
    query = select(Job).where(Job.project_id == project_id)
    
    if state:
        query = query.where(Job.state == state)
    
    query = query.offset(skip).limit(limit)
    
    result = await db.execute(query)
    return result.scalars().all()
