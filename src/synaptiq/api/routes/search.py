"""
Search API routes.

Supports both authenticated (JWT) and legacy (user_id in body) modes.
"""

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from synaptiq.api.dependencies import get_embedder, get_qdrant
from synaptiq.api.middleware.auth import get_current_user_optional
from synaptiq.domain.models import User
from synaptiq.processors.embedder import EmbeddingGenerator
from synaptiq.storage.qdrant import QdrantStore

router = APIRouter(prefix="/api/v1/search", tags=["Search"])


class SearchRequest(BaseModel):
    """Request body for search."""

    query: str = Field(..., description="Search query text", min_length=1)
    user_id: Optional[str] = Field(
        None,
        description="User ID (deprecated: use JWT authentication instead)",
    )
    limit: int = Field(default=10, ge=1, le=100, description="Maximum results")
    source_type: Optional[str] = Field(
        None,
        description="Filter by source type (youtube, web_article)",
    )
    has_definition: Optional[bool] = Field(
        None,
        description="Filter for chunks containing definitions",
    )
    concepts: Optional[list[str]] = Field(
        None,
        description="Filter by concepts (any match)",
    )
    score_threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Minimum similarity score",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "query": "What is a tensor?",
                "limit": 10,
                "has_definition": True,
            }
        }


def _get_user_id_for_search(request_body: SearchRequest, user: Optional[User]) -> str:
    """Get user_id from JWT or request body (legacy)."""
    if user:
        return user.id
    if request_body.user_id:
        return request_body.user_id
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required. Provide JWT token or user_id in body.",
    )


class SearchResult(BaseModel):
    """A single search result."""

    id: str = Field(..., description="Chunk ID")
    score: float = Field(..., description="Similarity score (0-1)")
    text: str = Field(..., description="Chunk text content")
    source_type: str = Field(..., description="Source type")
    source_url: str = Field(..., description="Original source URL")
    source_title: str = Field(..., description="Source title")
    timestamp_start_ms: Optional[int] = Field(None, description="Video start time (ms)")
    timestamp_end_ms: Optional[int] = Field(None, description="Video end time (ms)")
    citation_url: Optional[str] = Field(None, description="URL with timestamp for citation")
    concepts: list[str] = Field(default_factory=list, description="Extracted concepts")
    has_definition: bool = Field(default=False, description="Contains a definition")


class SearchResponse(BaseModel):
    """Response for search request."""

    query: str = Field(..., description="Original query")
    results: list[SearchResult] = Field(..., description="Search results")
    total: int = Field(..., description="Number of results returned")


@router.post(
    "",
    response_model=SearchResponse,
    summary="Search knowledge base",
    description="Semantic search across ingested content with filtering. Use JWT authentication or provide user_id in body (deprecated).",
)
async def search(
    request: SearchRequest,
    qdrant: QdrantStore = Depends(get_qdrant),
    embedder: EmbeddingGenerator = Depends(get_embedder),
    user: Optional[User] = Depends(get_current_user_optional),
) -> SearchResponse:
    """
    Search the knowledge base using semantic similarity.
    
    Features:
    - Vector similarity search with OpenAI embeddings
    - Multi-tenant filtering by user_id
    - Optional filters: source_type, has_definition, concepts
    - Score threshold for quality control
    
    Authentication: JWT token (preferred) or user_id in request body (deprecated).
    """
    user_id = _get_user_id_for_search(request, user)
    
    # Generate query embedding
    try:
        query_vector = await embedder.generate_single(request.query)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate query embedding: {str(e)}",
        )

    # Search Qdrant
    try:
        results = await qdrant.search(
            query_vector=query_vector,
            user_id=user_id,
            limit=request.limit,
            source_type=request.source_type,
            has_definition=request.has_definition,
            concepts=request.concepts,
            score_threshold=request.score_threshold,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}",
        )

    # Format results
    search_results = []
    for hit in results:
        payload = hit["payload"]
        
        # Build citation URL with timestamp for YouTube
        citation_url = payload.get("source_url")
        if payload.get("source_type") == "youtube" and payload.get("timestamp_start_ms"):
            seconds = payload["timestamp_start_ms"] // 1000
            citation_url = f"{citation_url}&t={seconds}s"

        search_results.append(
            SearchResult(
                id=hit["id"],
                score=hit["score"],
                text=payload.get("text", ""),
                source_type=payload.get("source_type", ""),
                source_url=payload.get("source_url", ""),
                source_title=payload.get("source_title", ""),
                timestamp_start_ms=payload.get("timestamp_start_ms"),
                timestamp_end_ms=payload.get("timestamp_end_ms"),
                citation_url=citation_url,
                concepts=payload.get("concepts", []),
                has_definition=payload.get("has_definition", False),
            )
        )

    return SearchResponse(
        query=request.query,
        results=search_results,
        total=len(search_results),
    )


@router.get(
    "/definitions",
    response_model=SearchResponse,
    summary="Search for definitions",
    description="Search specifically for definition chunks. Use JWT authentication or provide user_id query param (deprecated).",
)
async def search_definitions(
    query: str = Query(..., description="Concept to find definition for"),
    user_id: Optional[str] = Query(None, description="User ID (deprecated: use JWT)"),
    limit: int = Query(default=5, ge=1, le=20),
    qdrant: QdrantStore = Depends(get_qdrant),
    embedder: EmbeddingGenerator = Depends(get_embedder),
    user: Optional[User] = Depends(get_current_user_optional),
) -> SearchResponse:
    """
    Search for definitions of a concept.
    
    Filters results to chunks marked as containing definitions.
    Useful for "What is X?" style queries.
    
    Authentication: JWT token (preferred) or user_id query param (deprecated).
    """
    # Determine user_id from JWT or query param
    effective_user_id = user.id if user else user_id
    if not effective_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Provide JWT token or user_id query param.",
        )
    
    request = SearchRequest(
        query=f"definition of {query}",
        user_id=effective_user_id,
        limit=limit,
        has_definition=True,
        score_threshold=0.4,
    )

    return await search(request, qdrant, embedder, user)


