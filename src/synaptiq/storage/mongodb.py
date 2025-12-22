"""
MongoDB metadata store for documents, jobs, and concepts.
"""

from datetime import datetime
from typing import Any, Optional

import structlog
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING, IndexModel
from pymongo.errors import DuplicateKeyError

from config.settings import get_settings
from synaptiq.core.exceptions import StorageError
from synaptiq.core.schemas import CanonicalDocument, Job, JobStatus

logger = structlog.get_logger(__name__)


class MongoDBStore:
    """
    Async MongoDB client for metadata storage.
    
    Collections:
    - sources: Raw documents and metadata
    - jobs: Async job status tracking
    - concepts: Concept index (optional)
    """

    def __init__(
        self,
        uri: Optional[str] = None,
        database: Optional[str] = None,
    ):
        """
        Initialize the MongoDB store.
        
        Args:
            uri: MongoDB connection URI (default from settings)
            database: Database name (default from settings)
        """
        settings = get_settings()
        self.uri = uri or settings.mongodb_uri
        self.database_name = database or settings.mongodb_database

        self.client = AsyncIOMotorClient(self.uri)
        self.db: AsyncIOMotorDatabase = self.client[self.database_name]

        # Collections
        self.sources = self.db["sources"]
        self.jobs = self.db["jobs"]
        self.concepts = self.db["concepts"]

        logger.info(
            "MongoDBStore initialized",
            database=self.database_name,
        )

    async def ensure_indexes(self) -> None:
        """Create indexes for efficient queries."""
        try:
            # Sources collection indexes
            await self.sources.create_indexes([
                IndexModel([("id", ASCENDING)], unique=True),
                IndexModel([("user_id", ASCENDING)]),
                IndexModel([("source_type", ASCENDING)]),
                IndexModel([("source_url", ASCENDING)]),
                IndexModel([("ingested_at", DESCENDING)]),
                IndexModel([("user_id", ASCENDING), ("source_type", ASCENDING)]),
            ])

            # Jobs collection indexes
            await self.jobs.create_indexes([
                IndexModel([("id", ASCENDING)], unique=True),
                IndexModel([("user_id", ASCENDING)]),
                IndexModel([("status", ASCENDING)]),
                IndexModel([("created_at", DESCENDING)]),
                IndexModel([("user_id", ASCENDING), ("status", ASCENDING)]),
            ])

            # Concepts collection indexes
            await self.concepts.create_indexes([
                IndexModel([("concept_name", ASCENDING)]),
                IndexModel([("user_id", ASCENDING)]),
                IndexModel([
                    ("user_id", ASCENDING),
                    ("concept_name", ASCENDING),
                ], unique=True),
            ])

            logger.info("MongoDB indexes created")

        except Exception as e:
            logger.error("Failed to create indexes", error=str(e))
            raise StorageError(
                message=f"Failed to create MongoDB indexes: {str(e)}",
                store_type="mongodb",
                operation="ensure_indexes",
                cause=e,
            )

    # ===================
    # Sources Operations
    # ===================

    async def save_source(self, document: CanonicalDocument) -> str:
        """
        Save a canonical document to the sources collection.
        
        Args:
            document: The document to save
            
        Returns:
            Document ID
        """
        try:
            doc_dict = document.model_dump()
            doc_dict["_id"] = document.id

            await self.sources.replace_one(
                {"_id": document.id},
                doc_dict,
                upsert=True,
            )

            logger.info("Saved source", document_id=document.id)
            return document.id

        except Exception as e:
            logger.error("Failed to save source", error=str(e))
            raise StorageError(
                message=f"Failed to save source: {str(e)}",
                store_type="mongodb",
                operation="save_source",
                cause=e,
            )

    async def get_source(self, document_id: str) -> Optional[CanonicalDocument]:
        """
        Get a source document by ID.
        
        Args:
            document_id: Document ID
            
        Returns:
            CanonicalDocument or None
        """
        try:
            doc = await self.sources.find_one({"id": document_id})
            if doc:
                doc.pop("_id", None)
                return CanonicalDocument(**doc)
            return None

        except Exception as e:
            logger.error("Failed to get source", document_id=document_id, error=str(e))
            raise StorageError(
                message=f"Failed to get source: {str(e)}",
                store_type="mongodb",
                operation="get_source",
                cause=e,
            )

    async def list_sources(
        self,
        user_id: str,
        source_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """
        List sources for a user.
        
        Args:
            user_id: User ID
            source_type: Optional filter by source type
            limit: Maximum results
            offset: Pagination offset
            
        Returns:
            List of source summaries
        """
        try:
            query = {"user_id": user_id}
            if source_type:
                query["source_type"] = source_type

            cursor = self.sources.find(
                query,
                {
                    "_id": 0,
                    "id": 1,
                    "source_type": 1,
                    "source_url": 1,
                    "source_title": 1,
                    "ingested_at": 1,
                },
            ).sort("ingested_at", DESCENDING).skip(offset).limit(limit)

            return await cursor.to_list(length=limit)

        except Exception as e:
            logger.error("Failed to list sources", error=str(e))
            raise StorageError(
                message=f"Failed to list sources: {str(e)}",
                store_type="mongodb",
                operation="list_sources",
                cause=e,
            )

    async def delete_source(self, document_id: str, user_id: str) -> bool:
        """
        Delete a source document.
        
        Args:
            document_id: Document ID
            user_id: User ID for safety check
            
        Returns:
            True if deleted, False if not found
        """
        try:
            result = await self.sources.delete_one({
                "id": document_id,
                "user_id": user_id,
            })
            return result.deleted_count > 0

        except Exception as e:
            logger.error("Failed to delete source", error=str(e))
            raise StorageError(
                message=f"Failed to delete source: {str(e)}",
                store_type="mongodb",
                operation="delete_source",
                cause=e,
            )

    async def source_exists(self, source_url: str, user_id: str) -> Optional[str]:
        """
        Check if a source URL has already been ingested.
        
        Args:
            source_url: Source URL to check
            user_id: User ID
            
        Returns:
            Document ID if exists, None otherwise
        """
        try:
            doc = await self.sources.find_one(
                {"source_url": source_url, "user_id": user_id},
                {"id": 1},
            )
            return doc["id"] if doc else None

        except Exception as e:
            logger.error("Failed to check source exists", error=str(e))
            return None

    # =================
    # Jobs Operations
    # =================

    async def create_job(self, job: Job) -> str:
        """
        Create a new job.
        
        Args:
            job: Job to create
            
        Returns:
            Job ID
        """
        try:
            job_dict = job.model_dump()
            job_dict["_id"] = job.id

            await self.jobs.insert_one(job_dict)
            logger.info("Created job", job_id=job.id)
            return job.id

        except DuplicateKeyError:
            logger.warning("Job already exists", job_id=job.id)
            return job.id

        except Exception as e:
            logger.error("Failed to create job", error=str(e))
            raise StorageError(
                message=f"Failed to create job: {str(e)}",
                store_type="mongodb",
                operation="create_job",
                cause=e,
            )

    async def get_job(self, job_id: str) -> Optional[Job]:
        """
        Get a job by ID.
        
        Args:
            job_id: Job ID
            
        Returns:
            Job or None
        """
        try:
            doc = await self.jobs.find_one({"id": job_id})
            if doc:
                doc.pop("_id", None)
                return Job(**doc)
            return None

        except Exception as e:
            logger.error("Failed to get job", job_id=job_id, error=str(e))
            raise StorageError(
                message=f"Failed to get job: {str(e)}",
                store_type="mongodb",
                operation="get_job",
                cause=e,
            )

    async def update_job(
        self,
        job_id: str,
        status: Optional[JobStatus] = None,
        document_id: Optional[str] = None,
        error_message: Optional[str] = None,
        chunks_processed: Optional[int] = None,
    ) -> bool:
        """
        Update a job's status and metadata.
        
        Args:
            job_id: Job ID
            status: New status
            document_id: Resulting document ID
            error_message: Error message if failed
            chunks_processed: Number of chunks processed
            
        Returns:
            True if updated
        """
        try:
            update = {"$set": {"updated_at": datetime.utcnow()}}

            if status:
                update["$set"]["status"] = status.value
                if status == JobStatus.COMPLETED:
                    update["$set"]["completed_at"] = datetime.utcnow()

            if document_id:
                update["$set"]["document_id"] = document_id

            if error_message:
                update["$set"]["error_message"] = error_message

            if chunks_processed is not None:
                update["$set"]["chunks_processed"] = chunks_processed

            result = await self.jobs.update_one({"id": job_id}, update)
            return result.modified_count > 0

        except Exception as e:
            logger.error("Failed to update job", job_id=job_id, error=str(e))
            raise StorageError(
                message=f"Failed to update job: {str(e)}",
                store_type="mongodb",
                operation="update_job",
                cause=e,
            )

    async def list_jobs(
        self,
        user_id: str,
        status: Optional[JobStatus] = None,
        limit: int = 50,
    ) -> list[Job]:
        """
        List jobs for a user.
        
        Args:
            user_id: User ID
            status: Optional status filter
            limit: Maximum results
            
        Returns:
            List of jobs
        """
        try:
            query = {"user_id": user_id}
            if status:
                query["status"] = status.value

            cursor = self.jobs.find(query).sort("created_at", DESCENDING).limit(limit)
            docs = await cursor.to_list(length=limit)

            jobs = []
            for doc in docs:
                doc.pop("_id", None)
                jobs.append(Job(**doc))

            return jobs

        except Exception as e:
            logger.error("Failed to list jobs", error=str(e))
            raise StorageError(
                message=f"Failed to list jobs: {str(e)}",
                store_type="mongodb",
                operation="list_jobs",
                cause=e,
            )

    # ====================
    # Concepts Operations
    # ====================

    async def upsert_concept(
        self,
        user_id: str,
        concept_name: str,
        definition_chunk_id: Optional[str] = None,
        mention_chunk_ids: Optional[list[str]] = None,
    ) -> None:
        """
        Upsert a concept entry.
        
        Args:
            user_id: User ID
            concept_name: Concept name (lowercase)
            definition_chunk_id: Chunk ID containing definition
            mention_chunk_ids: List of chunk IDs mentioning this concept
        """
        try:
            concept_name = concept_name.lower().strip()

            update: dict[str, Any] = {
                "$set": {
                    "user_id": user_id,
                    "concept_name": concept_name,
                    "updated_at": datetime.utcnow(),
                },
                "$setOnInsert": {
                    "created_at": datetime.utcnow(),
                },
            }

            if definition_chunk_id:
                update["$set"]["definition_chunk_id"] = definition_chunk_id

            if mention_chunk_ids:
                update["$addToSet"] = {"mention_chunk_ids": {"$each": mention_chunk_ids}}

            await self.concepts.update_one(
                {"user_id": user_id, "concept_name": concept_name},
                update,
                upsert=True,
            )

        except Exception as e:
            logger.error("Failed to upsert concept", concept=concept_name, error=str(e))

    async def get_concept(
        self,
        user_id: str,
        concept_name: str,
    ) -> Optional[dict[str, Any]]:
        """
        Get a concept entry.
        
        Args:
            user_id: User ID
            concept_name: Concept name
            
        Returns:
            Concept document or None
        """
        try:
            concept_name = concept_name.lower().strip()
            doc = await self.concepts.find_one({
                "user_id": user_id,
                "concept_name": concept_name,
            })
            if doc:
                doc.pop("_id", None)
            return doc

        except Exception as e:
            logger.error("Failed to get concept", error=str(e))
            return None

    async def close(self) -> None:
        """Close the MongoDB connection."""
        self.client.close()


