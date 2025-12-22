"""
Celery application configuration.
"""

from celery import Celery

from config.settings import get_settings

settings = get_settings()

# Create Celery app
celery_app = Celery(
    "synaptiq",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["synaptiq.workers.tasks"],
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    
    # Task execution settings
    task_acks_late=True,  # Acknowledge after task completes
    task_reject_on_worker_lost=True,
    
    # Result settings
    result_expires=86400,  # Results expire after 24 hours
    
    # Worker settings
    worker_prefetch_multiplier=1,  # One task at a time per worker
    worker_concurrency=4,
    
    # Task routing
    task_routes={
        "synaptiq.workers.tasks.ingest_url_task": {"queue": "ingestion"},
        "synaptiq.workers.tasks.poll_supadata_job_task": {"queue": "polling"},
    },
    
    # Rate limiting
    task_annotations={
        "synaptiq.workers.tasks.ingest_url_task": {
            "rate_limit": "10/m",  # 10 per minute
        },
    },
    
    # Retry settings
    task_default_retry_delay=60,  # 1 minute
    task_max_retries=3,
)

# Optional: Configure task queues
celery_app.conf.task_queues = {
    "ingestion": {
        "exchange": "ingestion",
        "routing_key": "ingestion",
    },
    "polling": {
        "exchange": "polling", 
        "routing_key": "polling",
    },
    "celery": {
        "exchange": "celery",
        "routing_key": "celery",
    },
}


