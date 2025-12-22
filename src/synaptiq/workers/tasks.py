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
from synaptiq.processors.pipeline import create_default_pipeline
from synaptiq.storage.mongodb import MongoDBStore
from synaptiq.storage.qdrant import QdrantStore

logger = structlog.get_logger(__name__)


def run_async(coro):
    """Run an async function in a sync context."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


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
) -> dict:
    """
    Main ingestion task.
    
    Orchestrates the full ingestion pipeline:
    1. Get appropriate adapter
    2. Ingest content to CanonicalDocument
    3. Run processing pipeline
    4. Store in Qdrant and MongoDB
    5. Update job status
    
    Args:
        job_id: Job ID for tracking
        url: URL to ingest
        user_id: User ID for multi-tenant isolation
        source_type: Optional source type hint
        
    Returns:
        Result dict with document_id and chunk_count
    """
    return run_async(_ingest_url_async(self, job_id, url, user_id, source_type))


async def _ingest_url_async(
    task,
    job_id: str,
    url: str,
    user_id: str,
    source_type: Optional[str] = None,
) -> dict:
    """Async implementation of ingestion task."""
    mongo = MongoDBStore()
    qdrant = QdrantStore()
    
    try:
        logger.info(
            "Starting ingestion task",
            job_id=job_id,
            url=url,
            user_id=user_id,
        )

        # Update job status to processing
        await mongo.update_job(job_id, status=JobStatus.PROCESSING)

        # Ensure storage is ready
        await qdrant.ensure_collection()
        await mongo.ensure_indexes()

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
        logger.info("Running processing pipeline", document_id=document.id)
        pipeline = create_default_pipeline()
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
        )

        return {
            "status": "completed",
            "document_id": document.id,
            "chunk_count": chunk_count,
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


