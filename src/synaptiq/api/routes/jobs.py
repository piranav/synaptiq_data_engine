"""
Job status API routes.

All endpoints require JWT authentication.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from synaptiq.api.dependencies import get_mongodb
from synaptiq.api.middleware.auth import get_current_user
from synaptiq.core.schemas import Job, JobStatus
from synaptiq.domain.models import User
from synaptiq.storage.mongodb import MongoDBStore

router = APIRouter(prefix="/api/v1/jobs", tags=["Jobs"])


class JobResponse(BaseModel):
    """Response for job status."""

    id: str
    user_id: str
    source_url: str
    source_type: Optional[str]
    status: str
    document_id: Optional[str]
    error_message: Optional[str]
    chunks_processed: int
    created_at: str
    updated_at: str
    completed_at: Optional[str]


class JobListResponse(BaseModel):
    """Response for job listing."""

    jobs: list[JobResponse]
    total: int


def job_to_response(job: Job) -> JobResponse:
    """Convert Job model to response."""
    return JobResponse(
        id=job.id,
        user_id=job.user_id,
        source_url=job.source_url,
        source_type=job.source_type.value if job.source_type else None,
        status=job.status.value,
        document_id=job.document_id,
        error_message=job.error_message,
        chunks_processed=job.chunks_processed,
        created_at=job.created_at.isoformat(),
        updated_at=job.updated_at.isoformat(),
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
    )


@router.get(
    "/{job_id}",
    response_model=JobResponse,
    summary="Get job status",
    description="Get the status of an ingestion job.",
)
async def get_job(
    job_id: str,
    user: User = Depends(get_current_user),
    mongodb: MongoDBStore = Depends(get_mongodb),
) -> JobResponse:
    """
    Get the status of a specific ingestion job.
    
    Use this to poll for job completion after calling /ingest.
    Requires JWT authentication.
    """
    job = await mongodb.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {job_id}",
        )
    
    # Verify ownership
    if job.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this job",
        )

    return job_to_response(job)


@router.get(
    "",
    response_model=JobListResponse,
    summary="List jobs",
    description="List ingestion jobs for the authenticated user.",
)
async def list_jobs(
    user: User = Depends(get_current_user),
    status_filter: Optional[str] = Query(
        None,
        alias="status",
        description="Filter by status (pending, processing, completed, failed)",
    ),
    limit: int = Query(default=50, ge=1, le=100),
    mongodb: MongoDBStore = Depends(get_mongodb),
) -> JobListResponse:
    """
    List all ingestion jobs for the authenticated user.
    
    Optionally filter by job status.
    Requires JWT authentication.
    """
    # Parse status filter
    job_status = None
    if status_filter:
        try:
            job_status = JobStatus(status_filter)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status. Must be one of: {[s.value for s in JobStatus]}",
            )

    jobs = await mongodb.list_jobs(user.id, status=job_status, limit=limit)

    return JobListResponse(
        jobs=[job_to_response(job) for job in jobs],
        total=len(jobs),
    )


@router.delete(
    "/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel/delete a job",
    description="Cancel a pending job or delete a completed/failed job record.",
)
async def delete_job(
    job_id: str,
    user: User = Depends(get_current_user),
    mongodb: MongoDBStore = Depends(get_mongodb),
) -> None:
    """
    Delete a job record.
    
    Note: This only deletes the job tracking record.
    If the job has already processed content, the content remains.
    Requires JWT authentication.
    """
    job = await mongodb.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {job_id}",
        )

    if job.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this job",
        )

    # If job is processing, we can't really cancel it
    # But we can mark it as cancelled in the database
    if job.status == JobStatus.PROCESSING:
        await mongodb.update_job(
            job_id,
            status=JobStatus.FAILED,
            error_message="Job cancelled by user",
        )
    else:
        # Delete the job record
        await mongodb.jobs.delete_one({"id": job_id})


