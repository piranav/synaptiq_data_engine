"""
Ingestion API routes.

All endpoints require JWT authentication.

Supports:
- URL ingestion (YouTube, web articles)
- Note ingestion (direct text/markdown content)
- File upload (PDF, DOCX)
"""

from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from config.settings import get_settings
from synaptiq.adapters.base import AdapterFactory, normalize_url
from synaptiq.api.dependencies import get_mongodb
from synaptiq.api.middleware.auth import get_current_user
from synaptiq.core.schemas import Job, JobStatus, SourceType
from synaptiq.domain.models import User
from synaptiq.storage.mongodb import MongoDBStore
from synaptiq.storage.qdrant import QdrantStore
from synaptiq.storage.s3 import S3Store
from synaptiq.workers.tasks import ingest_url_task, ingest_note_task, ingest_file_task

router = APIRouter(prefix="/api/v1/ingest", tags=["Ingestion"])


class IngestRequest(BaseModel):
    """Request body for ingestion."""

    url: str = Field(..., description="URL to ingest (YouTube video or web article)")
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


class NoteIngestRequest(BaseModel):
    """Request body for note ingestion."""

    title: Optional[str] = Field(
        None,
        max_length=500,
        description="Note title (extracted from content if not provided)",
    )
    content: str = Field(
        ...,
        min_length=1,
        description="Note content in markdown or plain text format",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "title": "My Learning Notes",
                "content": "# Machine Learning Basics\n\nMachine learning is a subset of AI..."
            }
        }


class FileUploadResponse(BaseModel):
    """Response for file upload."""

    job_id: str = Field(..., description="Job ID for tracking")
    status: str = Field(..., description="Job status")
    filename: str = Field(..., description="Uploaded filename")
    source_type: str = Field(..., description="Detected file type")
    message: str = Field(..., description="Status message")
    s3_key: Optional[str] = Field(None, description="S3 object key (if S3 is enabled)")
    s3_url: Optional[str] = Field(None, description="S3 URL (if S3 is enabled)")


@router.post(
    "",
    response_model=IngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest a URL",
    description="Queue a URL for ingestion. Supports YouTube videos and web articles.",
)
async def ingest_url(
    request: IngestRequest,
    user: User = Depends(get_current_user),
    mongodb: MongoDBStore = Depends(get_mongodb),
) -> IngestResponse:
    """
    Ingest a URL into the knowledge base.
    
    - For YouTube URLs: Extracts transcript with timestamps
    - For web URLs: Scrapes article content
    
    Returns a job ID for tracking the ingestion status.
    Requires JWT authentication.
    """
    # Detect source type
    source_type = AdapterFactory.detect_source_type(request.url)
    if source_type is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported URL type. Supported: YouTube videos, web articles",
        )

    # Normalize URL to canonical form so Job and Source always match
    canonical_url = normalize_url(request.url)

    # Check if already ingested
    existing_id = await mongodb.source_exists(canonical_url, user.id)
    if existing_id:
        return IngestResponse(
            job_id="",
            status="already_exists",
            source_type=source_type.value,
            message=f"URL already ingested. Document ID: {existing_id}",
        )

    # Create job
    job = Job(
        user_id=user.id,
        source_url=canonical_url,
        source_type=source_type,
        status=JobStatus.PENDING,
    )
    await mongodb.create_job(job)

    # Queue the ingestion task
    ingest_url_task.delay(
        job_id=job.id,
        url=canonical_url,
        user_id=user.id,
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
    user: User = Depends(get_current_user),
    mongodb: MongoDBStore = Depends(get_mongodb),
) -> IngestSyncResponse:
    """
    Ingest a URL synchronously (blocking).
    
    Warning: This can take a long time for large content.
    Prefer async mode for production use.
    Requires JWT authentication.
    """
    from synaptiq.adapters.base import AdapterFactory, normalize_url
    from synaptiq.processors.pipeline import create_default_pipeline

    # Detect source type
    source_type = AdapterFactory.detect_source_type(request.url)
    if source_type is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported URL type",
        )

    # Normalize URL to canonical form
    canonical_url = normalize_url(request.url)

    # Check if already ingested
    existing_id = await mongodb.source_exists(canonical_url, user.id)
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
        adapter = AdapterFactory.get_adapter(canonical_url)
        document = await adapter.ingest(canonical_url, user.id)

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


# =============================================================================
# NOTE INGESTION
# =============================================================================


@router.post(
    "/note",
    response_model=IngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest a note",
    description="Queue a note (text/markdown content) for ingestion into the knowledge base.",
)
async def ingest_note(
    request: NoteIngestRequest,
    user: User = Depends(get_current_user),
    mongodb: MongoDBStore = Depends(get_mongodb),
) -> IngestResponse:
    """
    Ingest user-created note content into the knowledge base.
    
    - Accepts markdown or plain text content
    - Extracts concepts and relationships
    - Stores in vector and graph databases
    
    Returns a job ID for tracking the ingestion status.
    Requires JWT authentication.
    """
    # Generate a unique identifier for this note
    from uuid import uuid4
    note_id = str(uuid4())
    
    # Create job for tracking
    job = Job(
        user_id=user.id,
        source_url=f"note://{note_id}",
        source_type=SourceType.NOTE,
        status=JobStatus.PENDING,
    )
    await mongodb.create_job(job)

    # Queue the ingestion task
    ingest_note_task.delay(
        job_id=job.id,
        note_id=note_id,
        title=request.title,
        content=request.content,
        user_id=user.id,
    )

    return IngestResponse(
        job_id=job.id,
        status=JobStatus.PENDING.value,
        source_type=SourceType.NOTE.value,
        message="Note ingestion job queued successfully",
    )


@router.post(
    "/note/sync",
    response_model=IngestSyncResponse,
    summary="Ingest a note synchronously",
    description="Ingest a note and wait for completion.",
)
async def ingest_note_sync(
    request: NoteIngestRequest,
    user: User = Depends(get_current_user),
    mongodb: MongoDBStore = Depends(get_mongodb),
) -> IngestSyncResponse:
    """
    Ingest a note synchronously (blocking).
    
    Processes the note immediately and returns when complete.
    Requires JWT authentication.
    """
    from synaptiq.adapters.notes import NotesAdapter
    from synaptiq.processors.pipeline import create_default_pipeline

    try:
        # Use NotesAdapter to create document from content
        adapter = NotesAdapter()
        document = await adapter.ingest_content(
            content=request.content,
            user_id=user.id,
            title=request.title,
        )

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
            source_type=SourceType.NOTE.value,
            source_title=document.source_title,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Note ingestion failed: {str(e)}",
        )


# =============================================================================
# FILE UPLOAD INGESTION
# =============================================================================

ALLOWED_FILE_EXTENSIONS = {".pdf", ".docx"}
MAX_FILE_SIZE_MB = 50


@router.post(
    "/upload",
    response_model=FileUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload and ingest a file",
    description="Upload a PDF or DOCX file for ingestion into the knowledge base.",
)
async def ingest_file_upload(
    file: UploadFile = File(..., description="PDF or DOCX file to ingest"),
    user: User = Depends(get_current_user),
    mongodb: MongoDBStore = Depends(get_mongodb),
) -> FileUploadResponse:
    """
    Upload and ingest a PDF or DOCX file.
    
    - Maximum file size: 50MB
    - Supported formats: PDF, DOCX
    - Files are stored in S3 (if configured)
    - Extracts text, concepts, and relationships
    - Stores in vector and graph databases
    
    Returns a job ID for tracking the ingestion status.
    Requires JWT authentication.
    """
    import base64
    from pathlib import Path
    
    settings = get_settings()
    
    # Validate file extension
    filename = file.filename or "unnamed"
    file_ext = Path(filename).suffix.lower()
    
    if file_ext not in ALLOWED_FILE_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {file_ext}. Supported: {', '.join(ALLOWED_FILE_EXTENSIONS)}",
        )

    # Read file content
    file_content = await file.read()
    
    # Validate file size
    file_size_mb = len(file_content) / (1024 * 1024)
    if file_size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large: {file_size_mb:.1f}MB. Maximum: {MAX_FILE_SIZE_MB}MB",
        )

    # Determine source type
    source_type = SourceType.PDF if file_ext == ".pdf" else SourceType.DOCX
    
    # S3 upload information
    s3_key = None
    s3_url = None
    file_content_b64 = None
    
    # Upload to S3 if configured
    if settings.s3_enabled:
        try:
            s3_store = S3Store()
            await s3_store.ensure_bucket()
            s3_result = await s3_store.upload_file(
                file_content=file_content,
                filename=filename,
                user_id=user.id,
                content_type=file.content_type,
            )
            s3_key = s3_result["s3_key"]
            s3_url = s3_result["s3_url"]
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to upload file to S3: {str(e)}",
            )
    else:
        # Fallback: pass file content as base64 (not recommended for large files)
        file_content_b64 = base64.b64encode(file_content).decode('utf-8')

    # Create job for tracking
    job = Job(
        user_id=user.id,
        source_url=s3_url or f"file://{filename}",
        source_type=source_type,
        status=JobStatus.PENDING,
    )
    await mongodb.create_job(job)

    # Queue the ingestion task
    ingest_file_task.delay(
        job_id=job.id,
        filename=filename,
        file_content_b64=file_content_b64,  # None if S3 is used
        s3_key=s3_key,  # Used if S3 is enabled
        user_id=user.id,
        source_type=source_type.value,
    )

    return FileUploadResponse(
        job_id=job.id,
        status=JobStatus.PENDING.value,
        filename=filename,
        source_type=source_type.value,
        message="File upload ingestion job queued successfully",
        s3_key=s3_key,
        s3_url=s3_url,
    )


@router.post(
    "/upload/sync",
    response_model=IngestSyncResponse,
    summary="Upload and ingest a file synchronously",
    description="Upload a file and wait for ingestion to complete.",
)
async def ingest_file_upload_sync(
    file: UploadFile = File(..., description="PDF or DOCX file to ingest"),
    user: User = Depends(get_current_user),
    mongodb: MongoDBStore = Depends(get_mongodb),
) -> IngestSyncResponse:
    """
    Upload and ingest a file synchronously (blocking).
    
    Warning: This can take a long time for large files.
    Prefer async mode for production use.
    Requires JWT authentication.
    """
    from pathlib import Path
    from synaptiq.adapters.file import FileAdapter
    from synaptiq.processors.pipeline import create_default_pipeline

    # Validate file extension
    filename = file.filename or "unnamed"
    file_ext = Path(filename).suffix.lower()
    
    if file_ext not in ALLOWED_FILE_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {file_ext}. Supported: {', '.join(ALLOWED_FILE_EXTENSIONS)}",
        )

    # Read file content
    file_content = await file.read()
    
    # Validate file size
    file_size_mb = len(file_content) / (1024 * 1024)
    if file_size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large: {file_size_mb:.1f}MB. Maximum: {MAX_FILE_SIZE_MB}MB",
        )

    try:
        # Use FileAdapter to create document from file content
        adapter = FileAdapter()
        document = await adapter.ingest(
            source=file_content,
            user_id=user.id,
            filename=filename,
        )

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
            source_type=document.source_type.value,
            source_title=document.source_title,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"File ingestion failed: {str(e)}",
        )


# =============================================================================
# UTILITY ENDPOINTS
# =============================================================================


@router.get(
    "/supported-types",
    summary="Get supported source types",
    description="List all supported content types and their requirements.",
)
async def get_supported_types() -> dict:
    """Get list of supported source types."""
    return {
        "source_types": [
            {
                "type": "youtube",
                "description": "YouTube video transcripts",
                "endpoint": "POST /api/v1/ingest",
                "url_patterns": [
                    "youtube.com/watch?v=...",
                    "youtu.be/...",
                    "youtube.com/shorts/...",
                ],
            },
            {
                "type": "web_article",
                "description": "Web articles and blog posts",
                "endpoint": "POST /api/v1/ingest",
                "url_patterns": ["Any HTTP/HTTPS URL not matching other types"],
            },
            {
                "type": "note",
                "description": "User-created notes (markdown or plain text)",
                "endpoint": "POST /api/v1/ingest/note",
                "request_body": {"title": "optional", "content": "required"},
            },
            {
                "type": "pdf",
                "description": "PDF documents",
                "endpoint": "POST /api/v1/ingest/upload",
                "max_size_mb": MAX_FILE_SIZE_MB,
            },
            {
                "type": "docx",
                "description": "Microsoft Word documents",
                "endpoint": "POST /api/v1/ingest/upload",
                "max_size_mb": MAX_FILE_SIZE_MB,
            },
        ],
        "adapters": AdapterFactory.list_adapters(),
    }

