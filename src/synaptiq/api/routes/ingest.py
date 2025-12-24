"""
Ingestion API routes.

Supports both authenticated (JWT) and legacy (user_id in body) modes.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from synaptiq.adapters.base import AdapterFactory
from synaptiq.api.dependencies import get_mongodb
from synaptiq.api.middleware.auth import get_current_user_optional
from synaptiq.core.schemas import Job, JobStatus, SourceType
from synaptiq.domain.models import User
from synaptiq.storage.mongodb import MongoDBStore
from synaptiq.storage.qdrant import QdrantStore
from synaptiq.workers.tasks import ingest_url_task

router = APIRouter(prefix="/ingest", tags=["Ingestion"])


class IngestRequest(BaseModel):
    """Request body for ingestion."""

    url: str = Field(..., description="URL to ingest (YouTube video or web article)")
    user_id: Optional[str] = Field(
        None,
        description="User ID (deprecated: use JWT authentication instead)",
    )
    async_mode: bool = Field(
        default=True,
        description="If True, returns job ID immediately. If False, waits for completion.",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "url": "https://www.youtube.com/watch?v=aircAruvnKk",
                "async_mode": True,
            }
        }


class IngestResponse(BaseModel):
    """Response for ingestion request."""

    job_id: str = Field(..., description="Job ID for tracking")
    status: str = Field(..., description="Job status")
    source_type: Optional[str] = Field(None, description="Detected source type")
    message: str = Field(..., description="Status message")


class IngestSyncResponse(BaseModel):
    """Response for synchronous ingestion."""

    document_id: str = Field(..., description="Ingested document ID")
    chunk_count: int = Field(..., description="Number of chunks created")
    source_type: str = Field(..., description="Source type")
    source_title: str = Field(..., description="Source title")


def _get_user_id(request_body: IngestRequest, user: Optional[User]) -> str:
    """Get user_id from JWT or request body (legacy)."""
    if user:
        return user.id
    if request_body.user_id:
        return request_body.user_id
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required. Provide JWT token or user_id in body.",
    )


@router.post(
    "",
    response_model=IngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest a URL",
    description="Queue a URL for ingestion. Supports YouTube videos and web articles. Use JWT authentication or provide user_id in body (deprecated).",
)
async def ingest_url(
    request: IngestRequest,
    mongodb: MongoDBStore = Depends(get_mongodb),
    user: Optional[User] = Depends(get_current_user_optional),
) -> IngestResponse:
    """
    Ingest a URL into the knowledge base.
    
    - For YouTube URLs: Extracts transcript with timestamps
    - For web URLs: Scrapes article content
    
    Returns a job ID for tracking the ingestion status.
    
    Authentication: JWT token (preferred) or user_id in request body (deprecated).
    """
    user_id = _get_user_id(request, user)
    
    # Detect source type
    source_type = AdapterFactory.detect_source_type(request.url)
    if source_type is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported URL type. Supported: YouTube videos, web articles",
        )

    # Check if already ingested
    existing_id = await mongodb.source_exists(request.url, user_id)
    if existing_id:
        return IngestResponse(
            job_id="",
            status="already_exists",
            source_type=source_type.value,
            message=f"URL already ingested. Document ID: {existing_id}",
        )

    # Create job
    job = Job(
        user_id=user_id,
        source_url=request.url,
        source_type=source_type,
        status=JobStatus.PENDING,
    )
    await mongodb.create_job(job)

    # Queue the ingestion task
    ingest_url_task.delay(
        job_id=job.id,
        url=request.url,
        user_id=user_id,
        source_type=source_type.value,
    )

    return IngestResponse(
        job_id=job.id,
        status=JobStatus.PENDING.value,
        source_type=source_type.value,
        message="Ingestion job queued successfully",
    )


@router.post(
    "/sync",
    response_model=IngestSyncResponse,
    summary="Ingest a URL synchronously",
    description="Ingest a URL and wait for completion. Use for small content only.",
)
async def ingest_url_sync(
    request: IngestRequest,
    mongodb: MongoDBStore = Depends(get_mongodb),
    user: Optional[User] = Depends(get_current_user_optional),
) -> IngestSyncResponse:
    """
    Ingest a URL synchronously (blocking).
    
    Warning: This can take a long time for large content.
    Prefer async mode for production use.
    
    Authentication: JWT token (preferred) or user_id in request body (deprecated).
    """
    from synaptiq.adapters.base import AdapterFactory
    from synaptiq.api.dependencies import get_qdrant
    from synaptiq.processors.pipeline import create_default_pipeline

    user_id = _get_user_id(request, user)
    
    # Detect source type
    source_type = AdapterFactory.detect_source_type(request.url)
    if source_type is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported URL type",
        )

    # Check if already ingested
    existing_id = await mongodb.source_exists(request.url, user_id)
    if existing_id:
        doc = await mongodb.get_source(existing_id)
        if doc:
            return IngestSyncResponse(
                document_id=existing_id,
                chunk_count=0,
                source_type=source_type.value,
                source_title=doc.source_title,
            )

    try:
        # Get adapter and ingest
        adapter = AdapterFactory.get_adapter(request.url)
        document = await adapter.ingest(request.url, user_id)

        # Save to MongoDB
        await mongodb.save_source(document)

        # Process through pipeline
        pipeline = create_default_pipeline()
        processed_chunks = await pipeline.run(document)

        # Store in Qdrant
        qdrant = QdrantStore()
        await qdrant.ensure_collection()
        chunk_count = await qdrant.upsert_chunks(processed_chunks)
        await qdrant.close()

        return IngestSyncResponse(
            document_id=document.id,
            chunk_count=chunk_count,
            source_type=source_type.value,
            source_title=document.source_title,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ingestion failed: {str(e)}",
        )


@router.get(
    "/supported-types",
    summary="Get supported source types",
    description="List all supported URL types and their adapters.",
)
async def get_supported_types() -> dict:
    """Get list of supported source types."""
    return {
        "source_types": [
            {
                "type": "youtube",
                "description": "YouTube video transcripts",
                "url_patterns": [
                    "youtube.com/watch?v=...",
                    "youtu.be/...",
                    "youtube.com/shorts/...",
                ],
            },
            {
                "type": "web_article",
                "description": "Web articles and blog posts",
                "url_patterns": ["Any HTTP/HTTPS URL not matching other types"],
            },
        ],
        "adapters": AdapterFactory.list_adapters(),
    }

