import shutil
import logging
from pathlib import Path
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import Job, Project
from app.services.local_storage import STORAGE_BASE

logger = logging.getLogger(__name__)

class CleanupService:
    """Service to handle deletion of old jobs and projects to maintain storage limits."""

    @staticmethod
    async def cleanup_old_jobs(db: AsyncSession):
        """
        Keeps only the most recent MAX_RETAINED_JOBS.
        Deletes both database records and filesystem data for older jobs.
        """
        try:
            # 1. Find jobs to delete (keep the N newest)
            stmt = (
                select(Job)
                .order_by(desc(Job.created_at))
                .offset(settings.MAX_RETAINED_JOBS)
            )
            result = await db.execute(stmt)
            jobs_to_delete = result.scalars().all()

            if not jobs_to_delete:
                return

            print(f"Cleanup: Found {len(jobs_to_delete)} old jobs to remove")

            for job in jobs_to_delete:
                await CleanupService._delete_job_files(job.id)
                await db.delete(job)

            await db.commit()
            print(f"Cleanup complete. Removed {len(jobs_to_delete)} jobs.")

        except Exception as e:
            logger.error(f"Error during job cleanup: {e}")
            print(f"Job cleanup failed: {e}")
            await db.rollback()

    @staticmethod
    async def cleanup_old_projects(db: AsyncSession):
        """
        Keeps only the most recent MAX_RETAINED_PROJECTS.
        Deletes associated jobs, artifacts, and filesystem data.
        """
        try:
            # 1. Find projects to delete
            stmt = (
                select(Project)
                .order_by(desc(Project.created_at))
                .offset(settings.MAX_RETAINED_PROJECTS)
            )
            result = await db.execute(stmt)
            projects_to_delete = result.scalars().all()

            if not projects_to_delete:
                return

            print(f"Cleanup: Found {len(projects_to_delete)} old projects to remove")

            for project in projects_to_delete:
                print(f"  Deleting project {project.id} ({project.name})...")
                
                # Associated jobs and artifacts will be deleted via DB cascade,
                # but we must manually remove files from disk for each job.
                job_stmt = select(Job.id).where(Job.project_id == project.id)
                job_result = await db.execute(job_stmt)
                job_ids = job_result.scalars().all()
                
                for job_id in job_ids:
                    await CleanupService._delete_job_files(job_id)

                await db.delete(project)

            await db.commit()
            print(f"Project cleanup complete. Removed {len(projects_to_delete)} projects.")

        except Exception as e:
            logger.error(f"Error during project cleanup: {e}")
            print(f"Project cleanup failed: {e}")
            await db.rollback()

    @staticmethod
    async def _delete_job_files(job_id: str):
        """Helper to remove filesystem directories for a job."""
        for category in ["inputs", "outputs"]:
            job_dir = STORAGE_BASE / category / job_id
            if job_dir.exists() and job_dir.is_dir():
                try:
                    shutil.rmtree(job_dir)
                    print(f"    Removed {category} directory: {job_dir}")
                except Exception as e:
                    logger.error(f"Failed to delete directory {job_dir}: {e}")
