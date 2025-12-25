"""
Search API routes for unified cross-domain search.

Provides endpoints for:
- Unified search across sources, notes, and concepts
- Domain-specific search
- Definition search
- Search suggestions
"""

from typing import Any, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from synaptiq.api.dependencies import get_embedder, get_qdrant, get_fuseki
from synaptiq.api.middleware.auth import get_current_user, get_current_user_optional
from synaptiq.domain.models import User
from synaptiq.infrastructure.database import get_async_session
from synaptiq.processors.embedder import EmbeddingGenerator
from synaptiq.services.search_service import SearchDomain, SearchService, UnifiedSearchResult
from synaptiq.storage.fuseki import FusekiStore
from synaptiq.storage.qdrant import QdrantStore

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/search", tags=["Search"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================


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


class UnifiedSearchRequest(BaseModel):
    """Request for unified cross-domain search."""
    
    query: str = Field(..., description="Search query", min_length=1)
    domains: Optional[list[str]] = Field(
        None,
        description="Domains to search: sources, notes, concepts (default: all)",
    )
    limit: int = Field(default=20, ge=1, le=100, description="Maximum total results")
    source_type: Optional[str] = Field(
        None,
        description="Filter sources by type",
    )


class SearchResult(BaseModel):
    """A single search result from vector store."""

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


class UnifiedSearchResultResponse(BaseModel):
    """A single unified search result."""
    
    id: str = Field(..., description="Result ID")
    domain: str = Field(..., description="Source domain: sources, notes, concepts")
    title: str = Field(..., description="Result title")
    content: str = Field(..., description="Content preview")
    score: float = Field(..., description="Relevance score (0-1)")
    url: Optional[str] = Field(None, description="URL if applicable")
    source_type: Optional[str] = Field(None, description="Source type")
    concepts: list[str] = Field(default_factory=list, description="Related concepts")
    metadata: dict = Field(default_factory=dict, description="Additional metadata")


class SearchResponse(BaseModel):
    """Response for search request."""

    query: str = Field(..., description="Original query")
    results: list[SearchResult] = Field(..., description="Search results")
    total: int = Field(..., description="Number of results returned")


class UnifiedSearchResponse(BaseModel):
    """Response for unified search."""
    
    query: str = Field(..., description="Original query")
    results: list[UnifiedSearchResultResponse]
    total: int = Field(..., description="Total results")
    domains_searched: list[str] = Field(..., description="Domains that were searched")


class SuggestionsResponse(BaseModel):
    """Search suggestions response."""
    
    query: str
    suggestions: list[str]


# =============================================================================
# DEPENDENCY INJECTION
# =============================================================================


async def get_search_service(
    session: AsyncSession = Depends(get_async_session),
    qdrant: QdrantStore = Depends(get_qdrant),
    fuseki: FusekiStore = Depends(get_fuseki),
    embedder: EmbeddingGenerator = Depends(get_embedder),
) -> SearchService:
    """Get SearchService instance."""
    return SearchService(
        session=session,
        qdrant=qdrant,
        fuseki=fuseki,
        embedder=embedder,
    )


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


def _convert_to_response(result: UnifiedSearchResult) -> UnifiedSearchResultResponse:
    """Convert internal result to response model."""
    return UnifiedSearchResultResponse(
        id=result.id,
        domain=result.domain,
        title=result.title,
        content=result.content,
        score=result.score,
        url=result.url,
        source_type=result.source_type,
        concepts=result.concepts,
        metadata=result.metadata,
    )


# =============================================================================
# UNIFIED SEARCH ENDPOINTS
# =============================================================================


@router.post(
    "/unified",
    response_model=UnifiedSearchResponse,
    summary="Unified cross-domain search",
    description="Search across sources, notes, and concepts simultaneously.",
)
async def unified_search(
    request: UnifiedSearchRequest,
    user: User = Depends(get_current_user),
    search_service: SearchService = Depends(get_search_service),
) -> UnifiedSearchResponse:
    """
    Search across all knowledge domains.
    
    Searches:
    - **Sources**: Vector store with ingested content
    - **Notes**: User-created notes
    - **Concepts**: Knowledge graph concepts
    
    Results are ranked by relevance and merged.
    """
    # Parse domains
    domains = None
    if request.domains:
        domains = []
        for d in request.domains:
            try:
                domains.append(SearchDomain(d.lower()))
            except ValueError:
                pass
    
    results = await search_service.unified_search(
        user_id=user.id,
        query=request.query,
        domains=domains,
        limit=request.limit,
        source_type=request.source_type,
    )
    
    # Determine which domains were searched
    domains_searched = request.domains or ["sources", "notes", "concepts"]
    
    return UnifiedSearchResponse(
        query=request.query,
        results=[_convert_to_response(r) for r in results],
        total=len(results),
        domains_searched=domains_searched,
    )


@router.get(
    "/unified",
    response_model=UnifiedSearchResponse,
    summary="Unified search (GET)",
)
async def unified_search_get(
    q: str = Query(..., min_length=1, description="Search query"),
    domains: Optional[str] = Query(
        None,
        description="Comma-separated domains: sources,notes,concepts",
    ),
    limit: int = Query(default=20, ge=1, le=100),
    source_type: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
    search_service: SearchService = Depends(get_search_service),
) -> UnifiedSearchResponse:
    """
    Unified search via GET request.
    
    Convenience endpoint for simple searches.
    """
    domain_list = None
    if domains:
        domain_list = [SearchDomain(d.strip()) for d in domains.split(",")]
    
    results = await search_service.unified_search(
        user_id=user.id,
        query=q,
        domains=domain_list,
        limit=limit,
        source_type=source_type,
    )
    
    domains_searched = domains.split(",") if domains else ["sources", "notes", "concepts"]
    
    return UnifiedSearchResponse(
        query=q,
        results=[_convert_to_response(r) for r in results],
        total=len(results),
        domains_searched=domains_searched,
    )


@router.get(
    "/suggestions",
    response_model=SuggestionsResponse,
    summary="Get search suggestions",
)
async def get_suggestions(
    q: str = Query(..., min_length=1, description="Partial query"),
    limit: int = Query(default=5, ge=1, le=10),
    user: User = Depends(get_current_user),
    search_service: SearchService = Depends(get_search_service),
) -> SuggestionsResponse:
    """
    Get search suggestions for autocomplete.
    
    Returns concept labels and note titles that match the partial query.
    """
    suggestions = await search_service.get_search_suggestions(
        user_id=user.id,
        query=q,
        limit=limit,
    )
    
    return SuggestionsResponse(
        query=q,
        suggestions=suggestions,
    )


# =============================================================================
# LEGACY SEARCH ENDPOINTS (maintained for compatibility)
# =============================================================================


@router.post(
    "",
    response_model=SearchResponse,
    summary="Search knowledge base (legacy)",
    description="Semantic search across ingested content. For unified search, use POST /search/unified.",
)
async def search(
    request: SearchRequest,
    qdrant: QdrantStore = Depends(get_qdrant),
    embedder: EmbeddingGenerator = Depends(get_embedder),
    user: Optional[User] = Depends(get_current_user_optional),
) -> SearchResponse:
    """
    Search the knowledge base using semantic similarity.
    
    This is the legacy endpoint. For unified cross-domain search,
    use POST /api/v1/search/unified.
    
    Features:
    - Vector similarity search with OpenAI embeddings
    - Multi-tenant filtering by user_id
    - Optional filters: source_type, has_definition, concepts
    - Score threshold for quality control
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
    description="Search specifically for definition chunks.",
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
    """
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


@router.get(
    "/concept/{concept_uri:path}",
    response_model=UnifiedSearchResponse,
    summary="Find content by concept",
)
async def search_by_concept(
    concept_uri: str,
    limit: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    search_service: SearchService = Depends(get_search_service),
) -> UnifiedSearchResponse:
    """
    Find all content related to a specific concept.
    
    Returns sources and notes that reference the concept.
    """
    results = await search_service.search_by_concept(
        user_id=user.id,
        concept_uri=concept_uri,
        limit=limit,
    )
    
    return UnifiedSearchResponse(
        query=concept_uri,
        results=[_convert_to_response(r) for r in results],
        total=len(results),
        domains_searched=["sources", "notes"],
    )
