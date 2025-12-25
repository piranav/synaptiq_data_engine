"""
Sources API routes for managing ingested content.

All endpoints require JWT authentication.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from synaptiq.api.dependencies import get_mongodb, get_qdrant
from synaptiq.api.middleware.auth import get_current_user
from synaptiq.domain.models import User
from synaptiq.storage.mongodb import MongoDBStore
from synaptiq.storage.qdrant import QdrantStore

router = APIRouter(prefix="/api/v1/sources", tags=["Sources"])


class SourceSummary(BaseModel):
    """Summary of an ingested source."""

    id: str
    source_type: str
    source_url: str
    source_title: str
    ingested_at: str


class SourceListResponse(BaseModel):
    """Response for source listing."""

    sources: list[SourceSummary]
    total: int


class SourceDetailResponse(BaseModel):
    """Detailed source information."""

    id: str
    user_id: str
    source_type: str
    source_url: str
    source_title: str
    source_metadata: dict
    ingested_at: str
    created_at: Optional[str]
    raw_content_preview: str = Field(..., description="First 500 chars of content")
    segment_count: int


@router.get(
    "",
    response_model=SourceListResponse,
    summary="List sources",
    description="List all ingested sources for the authenticated user.",
)
async def list_sources(
    user: User = Depends(get_current_user),
    source_type: Optional[str] = Query(None, description="Filter by source type"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    mongodb: MongoDBStore = Depends(get_mongodb),
) -> SourceListResponse:
    """
    List all ingested sources for the authenticated user.
    
    Returns summaries without full content.
    Requires JWT authentication.
    """
    sources = await mongodb.list_sources(
        user_id=user.id,
        source_type=source_type,
        limit=limit,
        offset=offset,
    )

    return SourceListResponse(
        sources=[
            SourceSummary(
                id=s["id"],
                source_type=s["source_type"],
                source_url=s["source_url"],
                source_title=s["source_title"],
                ingested_at=s["ingested_at"].isoformat() if hasattr(s["ingested_at"], "isoformat") else str(s["ingested_at"]),
            )
            for s in sources
        ],
        total=len(sources),
    )


@router.get(
    "/{source_id}",
    response_model=SourceDetailResponse,
    summary="Get source details",
    description="Get detailed information about an ingested source.",
)
async def get_source(
    source_id: str,
    user: User = Depends(get_current_user),
    mongodb: MongoDBStore = Depends(get_mongodb),
) -> SourceDetailResponse:
    """
    Get detailed information about an ingested source.
    
    Includes metadata and content preview.
    Requires JWT authentication.
    """
    doc = await mongodb.get_source(source_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source not found: {source_id}",
        )

    if doc.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this source",
        )

    return SourceDetailResponse(
        id=doc.id,
        user_id=doc.user_id,
        source_type=doc.source_type.value,
        source_url=doc.source_url,
        source_title=doc.source_title,
        source_metadata=doc.source_metadata,
        ingested_at=doc.ingested_at.isoformat(),
        created_at=doc.created_at.isoformat() if doc.created_at else None,
        raw_content_preview=doc.raw_content[:500] + "..." if len(doc.raw_content) > 500 else doc.raw_content,
        segment_count=len(doc.content_segments),
    )


@router.delete(
    "/{source_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a source",
    description="Delete a source and all its chunks from the knowledge base.",
)
async def delete_source(
    source_id: str,
    user: User = Depends(get_current_user),
    mongodb: MongoDBStore = Depends(get_mongodb),
    qdrant: QdrantStore = Depends(get_qdrant),
) -> None:
    """
    Delete a source and all associated chunks.
    
    This removes:
    - The source document from MongoDB
    - All vector chunks from Qdrant
    
    Requires JWT authentication.
    """
    # Verify ownership
    doc = await mongodb.get_source(source_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source not found: {source_id}",
        )

    if doc.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this source",
        )

    # Delete from Qdrant first (chunks)
    await qdrant.delete_by_document(source_id, user.id)

    # Delete from MongoDB (source document)
    await mongodb.delete_source(source_id, user.id)


@router.get(
    "/stats",
    summary="Get source statistics",
    description="Get statistics about ingested sources for the authenticated user.",
)
async def get_stats(
    user: User = Depends(get_current_user),
    mongodb: MongoDBStore = Depends(get_mongodb),
    qdrant: QdrantStore = Depends(get_qdrant),
) -> dict:
    """
    Get statistics about the user's knowledge base.
    
    Requires JWT authentication.
    """
    # Count sources by type
    pipeline = [
        {"$match": {"user_id": user.id}},
        {"$group": {"_id": "$source_type", "count": {"$sum": 1}}},
    ]
    
    type_counts = {}
    async for doc in mongodb.sources.aggregate(pipeline):
        type_counts[doc["_id"]] = doc["count"]

    # Get Qdrant collection info
    collection_info = await qdrant.get_collection_info()

    return {
        "sources_by_type": type_counts,
        "total_sources": sum(type_counts.values()),
        "vector_store": collection_info,
    }


