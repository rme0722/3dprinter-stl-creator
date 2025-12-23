from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid
import logging

from app.db.database import get_db
from app.models import Job, Project, PrinterProfile
from app.models.job import JobState, PipelineType
from app.schemas.job import JobCreate, JobResponse, JobUpdate, JobSubmit
from app.services.local_worker import process_job_immediately

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/projects/{project_id}/jobs", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    project_id: str,
    job: JobCreate,
    db: AsyncSession = Depends(get_db)
) -> Job:
    """Create a new job in DRAFT state"""
    logger.info(f"=== CREATE JOB ENDPOINT ===")
    logger.info(f"Project ID: {project_id}")
    logger.info(f"Job data: {job}")
    
    # Verify project exists
    logger.info("Checking if project exists...")
    project = await db.get(Project, project_id)
    if not project:
        logger.error(f"Project not found: {project_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    logger.info(f"Project found: {project.name}")
    
    # Verify printer profile exists
    logger.info(f"Checking printer profile: {job.printer_profile_id}")
    printer_profile = await db.get(PrinterProfile, job.printer_profile_id)
    if not printer_profile:
        logger.error(f"Printer profile not found: {job.printer_profile_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Printer profile not found"
        )
    logger.info(f"Printer profile found: {printer_profile.name}")
    
    logger.info("Creating job object...")
    db_job = Job(
        id=f"job_{uuid.uuid4().hex[:12]}",
        project_id=project_id,
        pipeline_type=job.pipeline_type,
        printer_profile_id=job.printer_profile_id,
        model_preset_id=job.model_preset_id,
        config=job.config or {},
        state=JobState.DRAFT
    )
    logger.info(f"Job object created with ID: {db_job.id}")
    
    logger.info("Adding job to database...")
    db.add(db_job)
    
    logger.info("Committing to database...")
    await db.commit()
    
    logger.info("Refreshing job object...")
    await db.refresh(db_job)
    
    logger.info("Job creation completed successfully")
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
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
) -> Job:
    """Submit a job for processing"""
    logger.info(f"=== JOB SUBMIT ENDPOINT ===")
    logger.info(f"Job ID: {job_id}")
    
    job = await db.get(Job, job_id)
    if not job:
        logger.error(f"Job not found: {job_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    logger.info(f"Job found - current state: {job.state}")
    logger.info(f"Job details: {job.__dict__}")
    
    if not job.can_transition_to(JobState.SUBMITTED):
        logger.error(f"Cannot submit job in state {job.state}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot submit job in state {job.state}"
        )
    
    logger.info("Updating job state to SUBMITTED")
    job.state = JobState.SUBMITTED
    job.submitted_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(job)
    
    logger.info(f"Job updated successfully - new state: {job.state}")
    
    # Trigger background processing
    logger.info("Adding background task for job processing")
    background_tasks.add_task(process_job_immediately, job_id)
    
    logger.info("Job submit endpoint completed successfully")
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
