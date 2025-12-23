"""
Qdrant vector store for storing and searching embeddings.
"""

from typing import Any, Optional
from uuid import UUID

import structlog
from qdrant_client import AsyncQdrantClient, models
from qdrant_client.http.exceptions import UnexpectedResponse

from config.settings import get_settings
from synaptiq.core.exceptions import StorageError
from synaptiq.core.schemas import ProcessedChunk

logger = structlog.get_logger(__name__)


class QdrantStore:
    """
    Async Qdrant client for vector storage and search.
    
    Features:
    - Multi-tenant filtering by user_id
    - Payload indexing for efficient filtering
    - Batch upsert operations
    - Semantic search with metadata filters
    """

    def __init__(
        self,
        url: Optional[str] = None,
        api_key: Optional[str] = None,
        collection_name: Optional[str] = None,
    ):
        """
        Initialize the Qdrant store.
        
        Args:
            url: Qdrant URL (default from settings)
            api_key: Qdrant API key (default from settings)
            collection_name: Collection name (default from settings)
        """
        settings = get_settings()
        self.url = url or settings.qdrant_url
        self.api_key = api_key or settings.qdrant_api_key
        self.collection_name = collection_name or settings.qdrant_collection_name
        self.dimensions = settings.embedding_dimensions

        self.client = AsyncQdrantClient(
            url=self.url,
            api_key=self.api_key,
        )

        logger.info(
            "QdrantStore initialized",
            url=self.url,
            collection=self.collection_name,
        )

    async def ensure_collection(self) -> None:
        """
        Ensure the collection exists with proper configuration.
        Creates if not exists, skips if exists.
        """
        try:
            collections = await self.client.get_collections()
            collection_names = [c.name for c in collections.collections]

            if self.collection_name in collection_names:
                logger.info("Collection already exists", collection=self.collection_name)
                return

            # Create collection with vector config
            await self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=self.dimensions,
                    distance=models.Distance.COSINE,
                ),
            )

            # Create payload indexes for efficient filtering
            await self._create_payload_indexes()

            logger.info("Collection created", collection=self.collection_name)

        except Exception as e:
            logger.error("Failed to ensure collection", error=str(e))
            raise StorageError(
                message=f"Failed to ensure Qdrant collection: {str(e)}",
                store_type="qdrant",
                operation="ensure_collection",
                cause=e,
            )

    async def _create_payload_indexes(self) -> None:
        """Create payload indexes for efficient filtering."""
        indexes = [
            ("user_id", models.PayloadSchemaType.KEYWORD),
            ("source_type", models.PayloadSchemaType.KEYWORD),
            ("document_id", models.PayloadSchemaType.KEYWORD),
            ("has_definition", models.PayloadSchemaType.BOOL),
            ("concepts", models.PayloadSchemaType.KEYWORD),
        ]

        for field_name, schema_type in indexes:
            try:
                await self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name=field_name,
                    field_schema=schema_type,
                )
                logger.debug("Created payload index", field=field_name)
            except UnexpectedResponse as e:
                # Index might already exist
                if "already exists" not in str(e).lower():
                    logger.warning(
                        "Failed to create payload index",
                        field=field_name,
                        error=str(e),
                    )

    async def upsert_chunks(self, chunks: list[ProcessedChunk]) -> int:
        """
        Upsert processed chunks to Qdrant.
        
        Args:
            chunks: List of processed chunks with embeddings
            
        Returns:
            Number of chunks upserted
        """
        if not chunks:
            return 0

        try:
            points = [
                models.PointStruct(
                    id=chunk.id,
                    vector=chunk.vector,
                    payload=chunk.to_qdrant_payload(),
                )
                for chunk in chunks
            ]

            await self.client.upsert(
                collection_name=self.collection_name,
                points=points,
            )

            logger.info("Upserted chunks to Qdrant", count=len(chunks))
            return len(chunks)

        except Exception as e:
            logger.error("Failed to upsert chunks", error=str(e))
            raise StorageError(
                message=f"Failed to upsert chunks: {str(e)}",
                store_type="qdrant",
                operation="upsert",
                cause=e,
            )

    async def search(
        self,
        query_vector: list[float],
        user_id: str,
        limit: int = 10,
        source_type: Optional[str] = None,
        has_definition: Optional[bool] = None,
        concepts: Optional[list[str]] = None,
        score_threshold: float = 0.0,
    ) -> list[dict[str, Any]]:
        """
        Search for similar chunks with filtering.
        
        Args:
            query_vector: Query embedding vector
            user_id: User ID for multi-tenant filtering (required)
            limit: Maximum results to return
            source_type: Filter by source type
            has_definition: Filter for definition chunks
            concepts: Filter by concepts (any match)
            score_threshold: Minimum similarity score
            
        Returns:
            List of search results with payload and score
        """
        # Build filter conditions
        must_conditions = [
            models.FieldCondition(
                key="user_id",
                match=models.MatchValue(value=user_id),
            )
        ]

        if source_type:
            must_conditions.append(
                models.FieldCondition(
                    key="source_type",
                    match=models.MatchValue(value=source_type),
                )
            )

        if has_definition is not None:
            must_conditions.append(
                models.FieldCondition(
                    key="has_definition",
                    match=models.MatchValue(value=has_definition),
                )
            )

        # Concepts filter: any match
        should_conditions = []
        if concepts:
            should_conditions = [
                models.FieldCondition(
                    key="concepts",
                    match=models.MatchValue(value=concept),
                )
                for concept in concepts
            ]

        query_filter = models.Filter(
            must=must_conditions,
            should=should_conditions if should_conditions else None,
        )

        try:
            results = await self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                query_filter=query_filter,
                limit=limit,
                score_threshold=score_threshold,
                with_payload=True,
            )

            # query_points returns QueryResponse object with points attribute
            points = results.points if hasattr(results, "points") else results

            return [
                {
                    "id": str(hit.id),
                    "score": hit.score,
                    "payload": hit.payload,
                }
                for hit in points
            ]

        except Exception as e:
            logger.error("Search failed", error=str(e))
            raise StorageError(
                message=f"Search failed: {str(e)}",
                store_type="qdrant",
                operation="search",
                cause=e,
            )

    async def delete_by_document(self, document_id: str, user_id: str) -> int:
        """
        Delete all chunks for a document.
        
        Args:
            document_id: Document ID to delete
            user_id: User ID for safety check
            
        Returns:
            Number of points deleted (estimated)
        """
        try:
            # First count how many points match
            count_result = await self.client.count(
                collection_name=self.collection_name,
                count_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_id",
                            match=models.MatchValue(value=document_id),
                        ),
                        models.FieldCondition(
                            key="user_id",
                            match=models.MatchValue(value=user_id),
                        ),
                    ]
                ),
            )

            # Delete the points
            await self.client.delete(
                collection_name=self.collection_name,
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="document_id",
                                match=models.MatchValue(value=document_id),
                            ),
                            models.FieldCondition(
                                key="user_id",
                                match=models.MatchValue(value=user_id),
                            ),
                        ]
                    )
                ),
            )

            logger.info(
                "Deleted document chunks",
                document_id=document_id,
                count=count_result.count,
            )
            return count_result.count

        except Exception as e:
            logger.error("Delete failed", document_id=document_id, error=str(e))
            raise StorageError(
                message=f"Delete failed: {str(e)}",
                store_type="qdrant",
                operation="delete",
                cause=e,
            )

    async def delete_by_user(self, user_id: str) -> int:
        """
        Delete all chunks for a user.
        
        Args:
            user_id: User ID to delete
            
        Returns:
            Number of points deleted (estimated)
        """
        try:
            count_result = await self.client.count(
                collection_name=self.collection_name,
                count_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="user_id",
                            match=models.MatchValue(value=user_id),
                        ),
                    ]
                ),
            )

            await self.client.delete(
                collection_name=self.collection_name,
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="user_id",
                                match=models.MatchValue(value=user_id),
                            ),
                        ]
                    )
                ),
            )

            logger.info("Deleted user chunks", user_id=user_id, count=count_result.count)
            return count_result.count

        except Exception as e:
            logger.error("Delete user failed", user_id=user_id, error=str(e))
            raise StorageError(
                message=f"Delete user failed: {str(e)}",
                store_type="qdrant",
                operation="delete_user",
                cause=e,
            )

    async def get_collection_info(self) -> dict[str, Any]:
        """Get collection statistics."""
        try:
            info = await self.client.get_collection(self.collection_name)
            return {
                "name": self.collection_name,
                "points_count": info.points_count,
                "vectors_count": getattr(info, "vectors_count", info.points_count),
                "status": info.status.value if hasattr(info.status, "value") else str(info.status),
            }
        except Exception as e:
            logger.error("Failed to get collection info", error=str(e))
            return {"error": str(e)}

    async def close(self) -> None:
        """Close the client connection."""
        await self.client.close()

