"""
Celery tasks for async ingestion processing.
"""

import asyncio
from typing import Optional

import structlog
from celery import shared_task

from synaptiq.adapters.base import AdapterFactory
from synaptiq.core.exceptions import AdapterError, ProcessingError, StorageError
from synaptiq.core.schemas import Job, JobStatus, SourceType
from synaptiq.processors.pipeline import create_default_pipeline, create_pipeline_without_ontology
from synaptiq.storage.mongodb import MongoDBStore
from synaptiq.storage.qdrant import QdrantStore
from synaptiq.storage.fuseki import FusekiStore
from synaptiq.ontology.graph_manager import GraphManager

logger = structlog.get_logger(__name__)


def run_async(coro):
    """Run an async function in a sync context."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ═══════════════════════════════════════════════════════════════════════════════
# USER LIFECYCLE TASKS
# ═══════════════════════════════════════════════════════════════════════════════

@shared_task(
    bind=True,
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    max_retries=3,
)
def onboard_user_task(self, user_id: str) -> dict:
    """
    Onboard a new user by creating their named graph.
    
    Creates:
    - Named graph in Fuseki: synaptiq.ai/users/{user_id}/graph
    - Graph initialized with ontology imports
    
    Args:
        user_id: User identifier
        
    Returns:
        Result dict with graph_uri
    """
    return run_async(_onboard_user_async(user_id))


async def _onboard_user_async(user_id: str) -> dict:
    """Async implementation of user onboarding."""
    graph_manager = GraphManager()
    
    try:
        logger.info("Onboarding user", user_id=user_id)
        
        graph_uri = await graph_manager.onboard_user(user_id)
        
        logger.info(
            "User onboarded successfully",
            user_id=user_id,
            graph_uri=graph_uri,
        )
        
        return {
            "status": "completed",
            "user_id": user_id,
            "graph_uri": graph_uri,
        }
        
    except Exception as e:
        logger.error("User onboarding failed", user_id=user_id, error=str(e))
        return {
            "status": "failed",
            "user_id": user_id,
            "error": str(e),
        }
        
    finally:
        await graph_manager.close()


@shared_task(
    bind=True,
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    max_retries=3,
)
def delete_user_task(self, user_id: str) -> dict:
    """
    Delete all user data (GDPR compliance).
    
    Deletes:
    - Named graph from Fuseki
    - All chunks from Qdrant (filtered by user_id)
    - All sources and jobs from MongoDB
    
    Args:
        user_id: User identifier
        
    Returns:
        Result dict with deletion counts
    """
    return run_async(_delete_user_async(user_id))


async def _delete_user_async(user_id: str) -> dict:
    """Async implementation of user deletion."""
    graph_manager = GraphManager()
    qdrant = QdrantStore()
    mongo = MongoDBStore()
    
    try:
        logger.info("Deleting user data", user_id=user_id)
        
        # Delete graph
        await graph_manager.delete_user_data(user_id)
        logger.info("Deleted user graph", user_id=user_id)
        
        # Delete vectors
        qdrant_count = await qdrant.delete_by_user(user_id)
        logger.info("Deleted user vectors", user_id=user_id, count=qdrant_count)
        
        # Delete sources
        sources_result = await mongo.sources.delete_many({"user_id": user_id})
        logger.info("Deleted user sources", user_id=user_id, count=sources_result.deleted_count)
        
        # Delete jobs
        jobs_result = await mongo.jobs.delete_many({"user_id": user_id})
        logger.info("Deleted user jobs", user_id=user_id, count=jobs_result.deleted_count)
        
        # Delete concepts (MongoDB concepts collection)
        concepts_result = await mongo.concepts.delete_many({"user_id": user_id})
        logger.info("Deleted user concepts", user_id=user_id, count=concepts_result.deleted_count)
        
        return {
            "status": "completed",
            "user_id": user_id,
            "deleted": {
                "graph": True,
                "vectors": qdrant_count,
                "sources": sources_result.deleted_count,
                "jobs": jobs_result.deleted_count,
                "concepts": concepts_result.deleted_count,
            },
        }
        
    except Exception as e:
        logger.error("User deletion failed", user_id=user_id, error=str(e))
        return {
            "status": "failed",
            "user_id": user_id,
            "error": str(e),
        }
        
    finally:
        await graph_manager.close()
        await qdrant.close()
        await mongo.close()


# ═══════════════════════════════════════════════════════════════════════════════
# INGESTION TASKS
# ═══════════════════════════════════════════════════════════════════════════════

@shared_task(
    bind=True,
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=3,
)
def ingest_url_task(
    self,
    job_id: str,
    url: str,
    user_id: str,
    source_type: Optional[str] = None,
    enable_ontology: bool = True,
) -> dict:
    """
    Main ingestion task.
    
    Orchestrates the full ingestion pipeline:
    1. Ensure user graph exists
    2. Get appropriate adapter
    3. Ingest content to CanonicalDocument
    4. Run processing pipeline (with or without ontology)
    5. Store in Qdrant and MongoDB
    6. Update job status
    
    Args:
        job_id: Job ID for tracking
        url: URL to ingest
        user_id: User ID for multi-tenant isolation
        source_type: Optional source type hint
        enable_ontology: Whether to write to graph store (default: True)
        
    Returns:
        Result dict with document_id and chunk_count
    """
    return run_async(_ingest_url_async(self, job_id, url, user_id, source_type, enable_ontology))


async def _ingest_url_async(
    task,
    job_id: str,
    url: str,
    user_id: str,
    source_type: Optional[str] = None,
    enable_ontology: bool = True,
) -> dict:
    """Async implementation of ingestion task."""
    mongo = MongoDBStore()
    qdrant = QdrantStore()
    fuseki: Optional[FusekiStore] = None
    
    try:
        logger.info(
            "Starting ingestion task",
            job_id=job_id,
            url=url,
            user_id=user_id,
            enable_ontology=enable_ontology,
        )

        # Update job status to processing
        await mongo.update_job(job_id, status=JobStatus.PROCESSING)

        # Ensure storage is ready
        await qdrant.ensure_collection()
        await mongo.ensure_indexes()
        
        # Initialize Fuseki if ontology is enabled
        if enable_ontology:
            fuseki = FusekiStore()
            try:
                await fuseki.ensure_dataset()
                
                # Ensure user graph exists
                if not await fuseki.user_graph_exists(user_id):
                    await fuseki.create_user_graph(user_id)
                    logger.info("Created user graph", user_id=user_id)
            except Exception as e:
                logger.warning(
                    "Fuseki not available, continuing without ontology",
                    error=str(e),
                )
                enable_ontology = False

        # Check if already ingested
        existing_id = await mongo.source_exists(url, user_id)
        if existing_id:
            logger.info("URL already ingested", url=url, document_id=existing_id)
            await mongo.update_job(
                job_id,
                status=JobStatus.COMPLETED,
                document_id=existing_id,
                error_message="URL already ingested (returning existing document)",
            )
            return {
                "status": "already_exists",
                "document_id": existing_id,
            }

        # Get appropriate adapter
        try:
            adapter = AdapterFactory.get_adapter(url)
        except Exception as e:
            logger.error("No adapter found", url=url, error=str(e))
            await mongo.update_job(
                job_id,
                status=JobStatus.FAILED,
                error_message=f"No adapter found for URL: {str(e)}",
            )
            return {"status": "failed", "error": str(e)}

        # Ingest content
        logger.info("Ingesting content", adapter=adapter.__class__.__name__)
        document = await adapter.ingest(url, user_id)

        # Save source document to MongoDB
        await mongo.save_source(document)

        # Run processing pipeline
        logger.info(
            "Running processing pipeline",
            document_id=document.id,
            enable_ontology=enable_ontology,
        )
        
        if enable_ontology:
            pipeline = create_default_pipeline()
        else:
            pipeline = create_pipeline_without_ontology()
            
        processed_chunks = await pipeline.run(document)

        # Store chunks in Qdrant
        chunk_count = await qdrant.upsert_chunks(processed_chunks)

        # Update job as completed
        await mongo.update_job(
            job_id,
            status=JobStatus.COMPLETED,
            document_id=document.id,
            chunks_processed=chunk_count,
        )

        logger.info(
            "Ingestion completed",
            job_id=job_id,
            document_id=document.id,
            chunk_count=chunk_count,
            ontology_enabled=enable_ontology,
        )

        return {
            "status": "completed",
            "document_id": document.id,
            "chunk_count": chunk_count,
            "ontology_enabled": enable_ontology,
        }

    except AdapterError as e:
        logger.error("Adapter error", job_id=job_id, error=str(e))
        await mongo.update_job(
            job_id,
            status=JobStatus.FAILED,
            error_message=f"Adapter error: {e.message}",
        )
        return {"status": "failed", "error": str(e)}

    except ProcessingError as e:
        logger.error("Processing error", job_id=job_id, error=str(e))
        await mongo.update_job(
            job_id,
            status=JobStatus.FAILED,
            error_message=f"Processing error: {e.message}",
        )
        return {"status": "failed", "error": str(e)}

    except StorageError as e:
        logger.error("Storage error", job_id=job_id, error=str(e))
        await mongo.update_job(
            job_id,
            status=JobStatus.FAILED,
            error_message=f"Storage error: {e.message}",
        )
        # Retry on storage errors
        raise task.retry(exc=e)

    except Exception as e:
        logger.error("Unexpected error", job_id=job_id, error=str(e))
        await mongo.update_job(
            job_id,
            status=JobStatus.FAILED,
            error_message=f"Unexpected error: {str(e)}",
        )
        return {"status": "failed", "error": str(e)}

    finally:
        await mongo.close()
        await qdrant.close()
        if fuseki:
            await fuseki.close()


# ═══════════════════════════════════════════════════════════════════════════════
# NOTE INGESTION TASK
# ═══════════════════════════════════════════════════════════════════════════════

@shared_task(
    bind=True,
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=3,
)
def ingest_note_task(
    self,
    job_id: str,
    note_id: str,
    title: Optional[str],
    content: str,
    user_id: str,
    enable_ontology: bool = True,
) -> dict:
    """
    Ingest user-created note content.
    
    Args:
        job_id: Job ID for tracking
        note_id: Unique note identifier
        title: Note title (optional)
        content: Note content (markdown/text)
        user_id: User ID for multi-tenant isolation
        enable_ontology: Whether to write to graph store (default: True)
        
    Returns:
        Result dict with document_id and chunk_count
    """
    return run_async(_ingest_note_async(self, job_id, note_id, title, content, user_id, enable_ontology))


async def _ingest_note_async(
    task,
    job_id: str,
    note_id: str,
    title: Optional[str],
    content: str,
    user_id: str,
    enable_ontology: bool = True,
) -> dict:
    """Async implementation of note ingestion task."""
    from synaptiq.adapters.notes import NotesAdapter
    from synaptiq.processors.pipeline import create_default_pipeline, create_pipeline_without_ontology
    
    mongo = MongoDBStore()
    qdrant = QdrantStore()
    fuseki: Optional[FusekiStore] = None
    
    try:
        logger.info(
            "Starting note ingestion task",
            job_id=job_id,
            note_id=note_id,
            user_id=user_id,
            content_length=len(content),
        )

        # Update job status to processing
        await mongo.update_job(job_id, status=JobStatus.PROCESSING)

        # Ensure storage is ready
        await qdrant.ensure_collection()
        await mongo.ensure_indexes()
        
        # Initialize Fuseki if ontology is enabled
        if enable_ontology:
            fuseki = FusekiStore()
            try:
                await fuseki.ensure_dataset()
                if not await fuseki.user_graph_exists(user_id):
                    await fuseki.create_user_graph(user_id)
                    logger.info("Created user graph", user_id=user_id)
            except Exception as e:
                logger.warning("Fuseki not available, continuing without ontology", error=str(e))
                enable_ontology = False

        # Create document using NotesAdapter
        adapter = NotesAdapter()
        document = await adapter.ingest_content(
            content=content,
            user_id=user_id,
            title=title,
            note_id=note_id,
        )

        # Save source document to MongoDB
        await mongo.save_source(document)

        # Run processing pipeline
        logger.info("Running processing pipeline", document_id=document.id)
        
        if enable_ontology:
            pipeline = create_default_pipeline()
        else:
            pipeline = create_pipeline_without_ontology()
            
        processed_chunks = await pipeline.run(document)

        # Store chunks in Qdrant
        chunk_count = await qdrant.upsert_chunks(processed_chunks)

        # Update job as completed
        await mongo.update_job(
            job_id,
            status=JobStatus.COMPLETED,
            document_id=document.id,
            chunks_processed=chunk_count,
        )

        logger.info(
            "Note ingestion completed",
            job_id=job_id,
            document_id=document.id,
            chunk_count=chunk_count,
        )

        return {
            "status": "completed",
            "document_id": document.id,
            "chunk_count": chunk_count,
        }

    except Exception as e:
        logger.error("Note ingestion failed", job_id=job_id, error=str(e))
        await mongo.update_job(
            job_id,
            status=JobStatus.FAILED,
            error_message=f"Note ingestion error: {str(e)}",
        )
        return {"status": "failed", "error": str(e)}

    finally:
        await mongo.close()
        await qdrant.close()
        if fuseki:
            await fuseki.close()


# ═══════════════════════════════════════════════════════════════════════════════
# FILE INGESTION TASK
# ═══════════════════════════════════════════════════════════════════════════════

@shared_task(
    bind=True,
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=3,
)
def ingest_file_task(
    self,
    job_id: str,
    filename: str,
    file_content_b64: Optional[str],
    user_id: str,
    source_type: str,
    s3_key: Optional[str] = None,
    enable_ontology: bool = True,
) -> dict:
    """
    Ingest uploaded file (PDF/DOCX).
    
    Files can be provided either as base64 content OR as S3 key.
    If s3_key is provided, the file is downloaded from S3.
    
    Args:
        job_id: Job ID for tracking
        filename: Original filename
        file_content_b64: Base64 encoded file content (None if using S3)
        user_id: User ID for multi-tenant isolation
        source_type: File type (pdf, docx)
        s3_key: S3 object key (if file is in S3)
        enable_ontology: Whether to write to graph store (default: True)
        
    Returns:
        Result dict with document_id and chunk_count
    """
    return run_async(_ingest_file_async(self, job_id, filename, file_content_b64, user_id, source_type, s3_key, enable_ontology))


async def _ingest_file_async(
    task,
    job_id: str,
    filename: str,
    file_content_b64: Optional[str],
    user_id: str,
    source_type: str,
    s3_key: Optional[str] = None,
    enable_ontology: bool = True,
) -> dict:
    """Async implementation of file ingestion task."""
    import base64
    from synaptiq.adapters.file import FileAdapter
    from synaptiq.processors.pipeline import create_default_pipeline, create_pipeline_without_ontology
    from synaptiq.storage.s3 import S3Store
    
    mongo = MongoDBStore()
    qdrant = QdrantStore()
    fuseki: Optional[FusekiStore] = None
    
    try:
        # Get file content - either from S3 or base64
        if s3_key:
            # Download from S3
            logger.info("Downloading file from S3", s3_key=s3_key)
            s3_store = S3Store()
            file_content = await s3_store.download_file(s3_key)
        elif file_content_b64:
            # Decode from base64
            file_content = base64.b64decode(file_content_b64)
        else:
            raise ValueError("Either s3_key or file_content_b64 must be provided")
        
        logger.info(
            "Starting file ingestion task",
            job_id=job_id,
            filename=filename,
            user_id=user_id,
            file_size=len(file_content),
            source_type=source_type,
            from_s3=bool(s3_key),
        )

        # Update job status to processing
        await mongo.update_job(job_id, status=JobStatus.PROCESSING)

        # Ensure storage is ready
        await qdrant.ensure_collection()
        await mongo.ensure_indexes()
        
        # Initialize Fuseki if ontology is enabled
        if enable_ontology:
            fuseki = FusekiStore()
            try:
                await fuseki.ensure_dataset()
                if not await fuseki.user_graph_exists(user_id):
                    await fuseki.create_user_graph(user_id)
                    logger.info("Created user graph", user_id=user_id)
            except Exception as e:
                logger.warning("Fuseki not available, continuing without ontology", error=str(e))
                enable_ontology = False

        # Create document using FileAdapter
        adapter = FileAdapter()
        document = await adapter.ingest(
            source=file_content,
            user_id=user_id,
            filename=filename,
        )

        # Save source document to MongoDB
        await mongo.save_source(document)

        # Run processing pipeline
        logger.info("Running processing pipeline", document_id=document.id)
        
        if enable_ontology:
            pipeline = create_default_pipeline()
        else:
            pipeline = create_pipeline_without_ontology()
            
        processed_chunks = await pipeline.run(document)

        # Store chunks in Qdrant
        chunk_count = await qdrant.upsert_chunks(processed_chunks)

        # Update job as completed
        await mongo.update_job(
            job_id,
            status=JobStatus.COMPLETED,
            document_id=document.id,
            chunks_processed=chunk_count,
        )

        logger.info(
            "File ingestion completed",
            job_id=job_id,
            document_id=document.id,
            chunk_count=chunk_count,
            filename=filename,
        )

        return {
            "status": "completed",
            "document_id": document.id,
            "chunk_count": chunk_count,
            "filename": filename,
        }

    except Exception as e:
        logger.error("File ingestion failed", job_id=job_id, filename=filename, error=str(e))
        await mongo.update_job(
            job_id,
            status=JobStatus.FAILED,
            error_message=f"File ingestion error: {str(e)}",
        )
        return {"status": "failed", "error": str(e)}

    finally:
        await mongo.close()
        await qdrant.close()
        if fuseki:
            await fuseki.close()


# ═══════════════════════════════════════════════════════════════════════════════
# GRAPH TASKS
# ═══════════════════════════════════════════════════════════════════════════════

@shared_task
def export_user_graph_task(user_id: str, format: str = "turtle") -> dict:
    """
    Export a user's knowledge graph.
    
    Args:
        user_id: User identifier
        format: Output format (turtle, json-ld, ntriples)
        
    Returns:
        Result dict with graph data
    """
    return run_async(_export_user_graph_async(user_id, format))


async def _export_user_graph_async(user_id: str, format: str) -> dict:
    """Async implementation of graph export."""
    graph_manager = GraphManager()
    
    try:
        logger.info("Exporting user graph", user_id=user_id, format=format)
        
        # Check if graph exists
        if not await graph_manager.fuseki.user_graph_exists(user_id):
            return {
                "status": "failed",
                "error": f"No graph found for user {user_id}",
            }
        
        graph_data = await graph_manager.export_graph(user_id, format)
        stats = await graph_manager.get_graph_statistics(user_id)
        
        return {
            "status": "completed",
            "user_id": user_id,
            "format": format,
            "data": graph_data,
            "stats": stats,
        }
        
    except Exception as e:
        logger.error("Graph export failed", user_id=user_id, error=str(e))
        return {
            "status": "failed",
            "user_id": user_id,
            "error": str(e),
        }
        
    finally:
        await graph_manager.close()


@shared_task
def get_graph_stats_task(user_id: str) -> dict:
    """
    Get statistics for a user's knowledge graph.
    
    Args:
        user_id: User identifier
        
    Returns:
        Result dict with graph statistics
    """
    return run_async(_get_graph_stats_async(user_id))


async def _get_graph_stats_async(user_id: str) -> dict:
    """Async implementation of graph stats."""
    graph_manager = GraphManager()
    
    try:
        stats = await graph_manager.get_graph_statistics(user_id)
        return {
            "status": "completed",
            "user_id": user_id,
            "stats": stats,
        }
        
    except Exception as e:
        logger.error("Get graph stats failed", user_id=user_id, error=str(e))
        return {
            "status": "failed",
            "user_id": user_id,
            "error": str(e),
        }
        
    finally:
        await graph_manager.close()


# ═══════════════════════════════════════════════════════════════════════════════
# UTILITY TASKS
# ═══════════════════════════════════════════════════════════════════════════════

@shared_task(
    bind=True,
    max_retries=60,  # Poll for up to 30 minutes (30s interval)
    default_retry_delay=30,
)
def poll_supadata_job_task(
    self,
    job_id: str,
    supadata_job_id: str,
    user_id: str,
) -> dict:
    """
    Poll for SUPADATA async job completion.
    
    Used for crawl operations that return a job ID.
    
    Args:
        job_id: Our internal job ID
        supadata_job_id: SUPADATA's job ID
        user_id: User ID
        
    Returns:
        Result dict
    """
    return run_async(_poll_supadata_job_async(self, job_id, supadata_job_id, user_id))


async def _poll_supadata_job_async(
    task,
    job_id: str,
    supadata_job_id: str,
    user_id: str,
) -> dict:
    """Async implementation of SUPADATA job polling."""
    from supadata import Supadata
    from config.settings import get_settings

    settings = get_settings()
    mongo = MongoDBStore()

    try:
        client = Supadata(api_key=settings.supadata_api_key)

        # Check job status
        # Note: This is a placeholder - actual SUPADATA job polling
        # would depend on their API for checking job status
        logger.info(
            "Polling SUPADATA job",
            job_id=job_id,
            supadata_job_id=supadata_job_id,
        )

        # Placeholder: In real implementation, check SUPADATA job status
        # result = await asyncio.to_thread(client.job.status, supadata_job_id)
        # 
        # if result.status == "processing":
        #     raise task.retry()
        # elif result.status == "completed":
        #     # Process the result
        #     pass
        # elif result.status == "failed":
        #     await mongo.update_job(job_id, status=JobStatus.FAILED, ...)

        return {
            "status": "polling_not_implemented",
            "message": "SUPADATA job polling is a placeholder",
        }

    except Exception as e:
        logger.error("Polling error", error=str(e))
        return {"status": "failed", "error": str(e)}

    finally:
        await mongo.close()


@shared_task
def cleanup_old_jobs_task(days: int = 30) -> dict:
    """
    Cleanup old completed/failed jobs.
    
    Args:
        days: Delete jobs older than this many days
        
    Returns:
        Result dict with deleted count
    """
    return run_async(_cleanup_old_jobs_async(days))


async def _cleanup_old_jobs_async(days: int) -> dict:
    """Async implementation of job cleanup."""
    from datetime import datetime, timedelta

    mongo = MongoDBStore()

    try:
        cutoff = datetime.utcnow() - timedelta(days=days)

        result = await mongo.jobs.delete_many({
            "status": {"$in": [JobStatus.COMPLETED.value, JobStatus.FAILED.value]},
            "created_at": {"$lt": cutoff},
        })

        logger.info("Cleaned up old jobs", deleted=result.deleted_count)
        return {"status": "completed", "deleted": result.deleted_count}

    except Exception as e:
        logger.error("Cleanup error", error=str(e))
        return {"status": "failed", "error": str(e)}

    finally:
        await mongo.close()


@shared_task
def initialize_fuseki_task() -> dict:
    """
    Initialize Fuseki dataset and load ontology.
    
    Call this task on application startup to ensure
    the graph store is ready.
    
    Returns:
        Result dict
    """
    return run_async(_initialize_fuseki_async())


async def _initialize_fuseki_async() -> dict:
    """Async implementation of Fuseki initialization."""
    fuseki = FusekiStore()
    
    try:
        logger.info("Initializing Fuseki")
        await fuseki.ensure_dataset()
        
        return {
            "status": "completed",
            "message": "Fuseki dataset initialized",
        }
        
    except Exception as e:
        logger.error("Fuseki initialization failed", error=str(e))
        return {
            "status": "failed",
            "error": str(e),
        }
        
    finally:
        await fuseki.close()
