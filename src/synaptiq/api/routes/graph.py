from typing import Any, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from synaptiq.api.dependencies import get_graph_manager
from synaptiq.api.middleware.auth import get_current_user_optional
from synaptiq.domain.models import User
from synaptiq.ontology.graph_manager import GraphManager

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/graph", tags=["Graph"])

class NeighborhoodResponse(BaseModel):
    """Response for concept neighborhood."""
    found: bool
    uri: str
    label: str
    definition: Optional[str] = None
    source: Optional[dict] = None
    relationships: dict[str, list[str]] = Field(default_factory=dict)

@router.get(
    "/neighborhood",
    response_model=NeighborhoodResponse,
    summary="Get concept neighborhood",
    description="Get a concept and its immediate neighborhood in the graph.",
)
async def get_neighborhood(
    concept_label: Optional[str] = Query(None, description="Label of the concept (defaults to root if None)"),
    user_id: Optional[str] = Query(None, description="User ID (deprecated: use JWT)"),
    user: Optional[User] = Depends(get_current_user_optional),
    graph_manager: GraphManager = Depends(get_graph_manager),
) -> NeighborhoodResponse:
    """
    Get graph neighborhood for a concept.
    """
    # Determine user_id
    effective_user_id = user.id if user else user_id
    if not effective_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )

    try:
        logger.info(
            "Fetching graph neighborhood",
            user_id=effective_user_id,
            concept_label=concept_label,
        )
        
        data = await graph_manager.get_concept_neighborhood(
            user_id=effective_user_id,
            concept_label=concept_label
        )
        
        # Count total children across all relationship types
        total_children = sum(len(v) for v in data.get("relationships", {}).values()) if data else 0
        
        logger.info(
            "Graph neighborhood fetched",
            user_id=effective_user_id,
            concept_label=concept_label,
            found=data.get("found") if data else False,
            relationships_count=len(data.get("relationships", {})) if data else 0,
            total_children=total_children,
            relationship_types=list(data.get("relationships", {}).keys()) if data else [],
        )
        
        if not data:
            return NeighborhoodResponse(
                found=False,
                uri="",
                label=concept_label or "Root",
                relationships={}
            )

        return NeighborhoodResponse(**data)
        
    except Exception as e:
        logger.error(
            "Graph traversal failed",
            user_id=effective_user_id,
            concept_label=concept_label,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Graph traversal failed: {str(e)}",
        )
