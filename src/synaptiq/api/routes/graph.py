"""
Graph API routes for knowledge graph visualization and traversal.

Provides endpoints for:
- Full graph data for visualization (Poincaré disk)
- Concept neighborhood exploration
- Graph statistics
- Concept CRUD operations
"""

import math
from typing import Any, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from synaptiq.api.dependencies import get_graph_manager
from synaptiq.api.middleware.auth import get_current_user, get_current_user_optional
from synaptiq.domain.models import User
from synaptiq.ontology.graph_manager import GraphManager

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/graph", tags=["Graph"])


# =============================================================================
# RESPONSE MODELS
# =============================================================================


class GraphNode(BaseModel):
    """Node in the knowledge graph visualization."""
    
    id: str = Field(..., description="Unique node identifier (URI)")
    label: str = Field(..., description="Display label")
    type: str = Field(default="concept", description="Legacy type field")
    nodeType: str = Field(default="instance", description="class or instance")
    entityType: str = Field(default="concept", description="concept, definition, source, chunk")
    sourceType: Optional[str] = Field(None, description="youtube, web_article, note, pdf (if entityType=source)")
    size: float = Field(default=10, description="Node size based on connections")
    x: float = Field(default=0, description="X position (Poincaré coordinate)")
    y: float = Field(default=0, description="Y position (Poincaré coordinate)")
    has_definition: bool = Field(default=False, description="Whether concept has definition")
    color: Optional[str] = Field(None, description="Node color hint")


class GraphEdge(BaseModel):
    """Edge in the knowledge graph visualization."""
    
    id: str = Field(..., description="Unique edge identifier")
    source: str = Field(..., description="Source node ID")
    target: str = Field(..., description="Target node ID")
    type: str = Field(..., description="Relationship type: isA, partOf, relatedTo, etc.")
    label: str = Field(default="", description="Human-readable edge label")
    weight: float = Field(default=1.0, description="Edge weight")


class GraphStats(BaseModel):
    """Statistics about the knowledge graph."""
    
    nodes: int = Field(default=0, description="Total node count")
    edges: int = Field(default=0, description="Total edge count")
    concepts: int = Field(default=0, description="Concept count")
    definitions: int = Field(default=0, description="Definition count")
    sources: int = Field(default=0, description="Source count")
    density: float = Field(default=0, description="Graph density")


class FullGraphResponse(BaseModel):
    """Response containing full graph data for visualization."""
    
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    stats: GraphStats = Field(default_factory=GraphStats)


class RelationshipTarget(BaseModel):
    """A target node in a relationship."""
    
    uri: str = Field(..., description="Target node URI")
    label: str = Field(..., description="Target node label")
    nodeType: str = Field(default="instance", description="class or instance")
    entityType: str = Field(default="concept", description="concept, definition, source")


class NeighborhoodResponse(BaseModel):
    """Response for concept neighborhood."""
    
    found: bool
    uri: str
    label: str
    nodeType: str = Field(default="instance", description="class or instance")
    entityType: str = Field(default="concept", description="concept, definition, source")
    sourceType: Optional[str] = Field(None, description="Source type if entityType=source")
    definition: Optional[str] = None
    source: Optional[dict] = None
    relationships: dict[str, list[str]] = Field(default_factory=dict)
    richRelationships: dict[str, list[RelationshipTarget]] = Field(
        default_factory=dict,
        description="Relationships with full target metadata"
    )


class JITTreeNode(BaseModel):
    """Node structure for JIT Hypertree visualization (Poincare disk)."""
    
    id: str = Field(..., description="Unique node identifier")
    name: str = Field(..., description="Display name")
    data: dict[str, Any] = Field(default_factory=dict, description="Node visual properties")
    children: list["JITTreeNode"] = Field(default_factory=list, description="Child nodes")


# Allow forward reference
JITTreeNode.model_rebuild()


class ConceptDetail(BaseModel):
    """Detailed information about a concept."""
    
    uri: str = Field(..., description="Concept URI")
    label: str = Field(..., description="Concept label")
    alt_labels: list[str] = Field(default_factory=list, description="Alternative labels")
    definition: Optional[str] = Field(None, description="Definition text")
    source_title: Optional[str] = Field(None, description="Source where defined")
    source_url: Optional[str] = Field(None, description="Source URL")
    relationships: dict[str, list[dict]] = Field(
        default_factory=dict,
        description="Relationships grouped by type",
    )
    created_at: Optional[str] = Field(None, description="When concept was created")


class ConceptListResponse(BaseModel):
    """Response for concept listing."""
    
    concepts: list[dict]
    total: int
    offset: int
    limit: int


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def compute_poincare_layout(
    nodes: list[dict],
    edges: list[dict],
    center_concept: Optional[str] = None,
) -> list[dict]:
    """
    Compute Poincaré disk layout for nodes.
    
    Places nodes in a hyperbolic space projection onto a unit disk.
    More connected nodes are placed toward the center.
    
    Args:
        nodes: List of node dicts
        edges: List of edge dicts
        center_concept: Optional concept to place at center
        
    Returns:
        Nodes with x, y coordinates added
    """
    if not nodes:
        return nodes
    
    # Count connections per node
    connection_counts = {n["id"]: 0 for n in nodes}
    for edge in edges:
        if edge["source"] in connection_counts:
            connection_counts[edge["source"]] += 1
        if edge["target"] in connection_counts:
            connection_counts[edge["target"]] += 1
    
    # Sort by connections (most connected first)
    max_connections = max(connection_counts.values()) if connection_counts else 1
    
    # Assign positions using a spiral pattern
    # More connected nodes get positions closer to center
    positioned_nodes = []
    
    for i, node in enumerate(nodes):
        connections = connection_counts.get(node["id"], 0)
        
        # Radius: more connections = closer to center
        # Use 1 - (connections / max) to invert (more = smaller radius)
        base_radius = 0.1 + 0.8 * (1 - connections / max(max_connections, 1))
        
        # Angle: distribute around the circle
        angle = (i / len(nodes)) * 2 * math.pi
        
        # Add some jitter based on index for visual variety
        radius = base_radius * (0.9 + 0.2 * ((i * 7) % 10) / 10)
        
        # Poincaré disk coordinates
        x = radius * math.cos(angle)
        y = radius * math.sin(angle)
        
        # Ensure within unit disk
        x = max(-0.95, min(0.95, x))
        y = max(-0.95, min(0.95, y))
        
        positioned_node = {
            **node,
            "x": round(x, 4),
            "y": round(y, 4),
            "size": 8 + (connections / max(max_connections, 1)) * 12,
        }
        positioned_nodes.append(positioned_node)
    
    return positioned_nodes


# =============================================================================
# FULL GRAPH ENDPOINTS
# =============================================================================


@router.get(
    "/full",
    response_model=FullGraphResponse,
    summary="Get full graph for visualization",
    description="Returns all nodes and edges formatted for Poincaré disk visualization.",
)
async def get_full_graph(
    user: User = Depends(get_current_user),
    graph_manager: GraphManager = Depends(get_graph_manager),
    limit: int = Query(default=500, ge=1, le=2000, description="Maximum nodes to return"),
) -> FullGraphResponse:
    """
    Get the full knowledge graph for visualization.
    
    Returns nodes with positions computed for Poincaré disk rendering,
    and edges with relationship types.
    
    Requires JWT authentication.
    """
    try:
        logger.info("Fetching full graph", user_id=user.id, limit=limit)
        
        # Get all concepts
        concepts_sparql = f"""
        SELECT ?concept ?label ?hasDefinition
        WHERE {{
            ?concept a syn:Concept ;
                     syn:label ?label .
            BIND(EXISTS {{ ?concept syn:hasDefinition ?def }} AS ?hasDefinition)
        }}
        LIMIT {limit}
        """
        
        concepts = await graph_manager.fuseki.query(user.id, concepts_sparql)
        
        # Build nodes
        nodes = []
        node_ids = set()
        
        for c in concepts:
            node_id = c.get("concept", "")
            if node_id and node_id not in node_ids:
                nodes.append({
                    "id": node_id,
                    "label": c.get("label", ""),
                    "type": "concept",
                    "nodeType": "instance",
                    "entityType": "concept",
                    "sourceType": None,
                    "has_definition": c.get("hasDefinition", "false") == "true",
                })
                node_ids.add(node_id)
        
        # Get all relationships
        edges_sparql = """
        SELECT ?source ?target ?relType
        WHERE {
            ?source a syn:Concept .
            ?target a syn:Concept .
            ?source ?relType ?target .
            FILTER(?relType IN (
                syn:isA, syn:partOf, syn:prerequisiteFor, 
                syn:relatedTo, syn:oppositeOf, syn:usedIn
            ))
        }
        """
        
        relationships = await graph_manager.fuseki.query(user.id, edges_sparql)
        
        # Human-readable labels for relationship types
        REL_LABELS = {
            "isA": "is a",
            "partOf": "part of",
            "prerequisiteFor": "prerequisite for",
            "relatedTo": "related to",
            "oppositeOf": "opposite of",
            "usedIn": "used in",
        }
        
        # Build edges
        edges = []
        edge_ids = set()
        
        for r in relationships:
            source = r.get("source", "")
            target = r.get("target", "")
            rel_type = r.get("relType", "").split("#")[-1]
            
            if source and target and source in node_ids and target in node_ids:
                edge_id = f"{source}_{rel_type}_{target}"
                if edge_id not in edge_ids:
                    edges.append({
                        "id": edge_id,
                        "source": source,
                        "target": target,
                        "type": rel_type,
                        "label": REL_LABELS.get(rel_type, rel_type),
                        "weight": 1.0,
                    })
                    edge_ids.add(edge_id)
        
        # Compute layout
        positioned_nodes = compute_poincare_layout(nodes, edges)
        
        # Calculate stats
        graph_stats = await graph_manager.get_graph_statistics(user.id)
        
        # Calculate density
        n = len(nodes)
        e = len(edges)
        max_edges = n * (n - 1) / 2 if n > 1 else 1
        density = e / max_edges if max_edges > 0 else 0
        
        stats = GraphStats(
            nodes=len(nodes),
            edges=len(edges),
            concepts=graph_stats.get("concept_count", len(nodes)),
            definitions=graph_stats.get("definition_count", 0),
            sources=graph_stats.get("source_count", 0),
            density=round(density, 4),
        )
        
        logger.info(
            "Full graph fetched",
            user_id=user.id,
            nodes=len(nodes),
            edges=len(edges),
        )
        
        return FullGraphResponse(
            nodes=[GraphNode(**n) for n in positioned_nodes],
            edges=[GraphEdge(**e) for e in edges],
            stats=stats,
        )
        
    except Exception as e:
        logger.error("Failed to get full graph", user_id=user.id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get graph: {str(e)}",
        )


@router.get(
    "/stats",
    response_model=GraphStats,
    summary="Get graph statistics",
)
async def get_graph_stats(
    user: User = Depends(get_current_user),
    graph_manager: GraphManager = Depends(get_graph_manager),
) -> GraphStats:
    """
    Get statistics about the user's knowledge graph.
    
    Requires JWT authentication.
    """
    try:
        stats = await graph_manager.get_graph_statistics(user.id)
        
        return GraphStats(
            nodes=stats.get("concept_count", 0),
            edges=0,  # Would need separate query
            concepts=stats.get("concept_count", 0),
            definitions=stats.get("definition_count", 0),
            sources=stats.get("source_count", 0),
            density=0,
        )
        
    except Exception as e:
        logger.error("Failed to get graph stats", user_id=user.id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get stats: {str(e)}",
        )


# =============================================================================
# CONCEPT ENDPOINTS
# =============================================================================


@router.get(
    "/concepts",
    response_model=ConceptListResponse,
    summary="List all concepts",
)
async def list_concepts(
    user: User = Depends(get_current_user),
    graph_manager: GraphManager = Depends(get_graph_manager),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    search: Optional[str] = Query(None, description="Search in labels"),
) -> ConceptListResponse:
    """
    List all concepts in the user's knowledge graph.
    
    Requires JWT authentication.
    """
    try:
        if search:
            # Search for matching concepts
            concepts = await graph_manager.fuseki.find_similar_concepts(
                user.id, search, limit=limit
            )
        else:
            # Get all concepts paginated
            concepts = await graph_manager.fuseki.get_user_concepts(
                user.id, limit=limit, offset=offset
            )
        
        return ConceptListResponse(
            concepts=concepts,
            total=len(concepts),
            offset=offset,
            limit=limit,
        )
        
    except Exception as e:
        logger.error("Failed to list concepts", user_id=user.id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list concepts: {str(e)}",
        )


@router.get(
    "/concepts/{concept_id:path}",
    response_model=ConceptDetail,
    summary="Get concept details",
)
async def get_concept(
    concept_id: str,
    user: User = Depends(get_current_user),
    graph_manager: GraphManager = Depends(get_graph_manager),
) -> ConceptDetail:
    """
    Get detailed information about a specific concept.
    
    The concept_id should be the full URI.
    
    Requires JWT authentication.
    """
    try:
        # Get concept with definition
        details = await graph_manager.fuseki.get_concept_with_definition(
            user.id, concept_id
        )
        
        if not details:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Concept not found: {concept_id}",
            )
        
        # Get relationships
        relationships_raw = await graph_manager.fuseki.get_concept_relationships(
            user.id, concept_id
        )
        
        # Group by relationship type
        relationships: dict[str, list[dict]] = {}
        for rel in relationships_raw:
            rel_type = rel.get("relationType", "").split("#")[-1]
            if rel_type not in relationships:
                relationships[rel_type] = []
            relationships[rel_type].append({
                "uri": rel.get("relatedConcept", ""),
                "label": rel.get("relatedLabel", ""),
            })
        
        return ConceptDetail(
            uri=concept_id,
            label=details.get("label", ""),
            definition=details.get("definitionText"),
            source_title=details.get("sourceTitle"),
            source_url=details.get("sourceUrl"),
            relationships=relationships,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get concept",
            user_id=user.id,
            concept_id=concept_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get concept: {str(e)}",
        )


@router.get(
    "/concepts/{concept_id:path}/neighborhood",
    response_model=FullGraphResponse,
    summary="Get concept neighborhood as subgraph",
)
async def get_concept_subgraph(
    concept_id: str,
    user: User = Depends(get_current_user),
    graph_manager: GraphManager = Depends(get_graph_manager),
    depth: int = Query(default=2, ge=1, le=5, description="Neighborhood depth"),
) -> FullGraphResponse:
    """
    Get subgraph around a concept.
    
    Returns nodes and edges within N hops of the specified concept.
    
    Requires JWT authentication.
    """
    try:
        # Get N-hop neighborhood via SPARQL property paths
        # For depth=1, get direct neighbors; for depth=2, neighbors of neighbors, etc.
        
        # Build property path pattern based on depth
        path_pattern = "?p" if depth == 1 else f"?p{{1,{depth}}}"
        
        neighborhood_sparql = f"""
        SELECT DISTINCT ?concept ?label ?connected ?connectedLabel ?relType
        WHERE {{
            VALUES ?center {{ <{concept_id}> }}
            
            {{
                ?center syn:label ?centerLabel .
                BIND(?center AS ?concept)
                BIND(?centerLabel AS ?label)
                
                ?center ?relType ?connected .
                ?connected a syn:Concept ;
                           syn:label ?connectedLabel .
                FILTER(?relType IN (
                    syn:isA, syn:partOf, syn:prerequisiteFor, 
                    syn:relatedTo, syn:oppositeOf, syn:usedIn
                ))
            }}
            UNION
            {{
                ?connected ?relType ?center .
                ?connected a syn:Concept ;
                           syn:label ?connectedLabel .
                
                ?center syn:label ?centerLabel .
                BIND(?center AS ?concept)
                BIND(?centerLabel AS ?label)
                FILTER(?relType IN (
                    syn:isA, syn:partOf, syn:prerequisiteFor, 
                    syn:relatedTo, syn:oppositeOf, syn:usedIn
                ))
            }}
        }}
        LIMIT 100
        """
        
        results = await graph_manager.fuseki.query(user.id, neighborhood_sparql)
        
        # Build nodes and edges from results
        nodes = {}
        edges = []
        edge_ids = set()
        
        # Add center node
        nodes[concept_id] = {
            "id": concept_id,
            "label": "",
            "type": "concept",
            "has_definition": False,
        }
        
        for r in results:
            concept = r.get("concept", "")
            label = r.get("label", "")
            connected = r.get("connected", "")
            connected_label = r.get("connectedLabel", "")
            rel_type = r.get("relType", "").split("#")[-1]
            
            # Update center label
            if concept == concept_id and label:
                nodes[concept_id]["label"] = label
            
            # Add connected node
            if connected and connected not in nodes:
                nodes[connected] = {
                    "id": connected,
                    "label": connected_label,
                    "type": "concept",
                    "has_definition": False,
                }
            
            # Add edge
            if concept and connected and rel_type:
                edge_id = f"{concept}_{rel_type}_{connected}"
                if edge_id not in edge_ids:
                    edges.append({
                        "id": edge_id,
                        "source": concept,
                        "target": connected,
                        "type": rel_type,
                        "weight": 1.0,
                    })
                    edge_ids.add(edge_id)
        
        # Compute layout
        node_list = list(nodes.values())
        positioned_nodes = compute_poincare_layout(node_list, edges, concept_id)
        
        return FullGraphResponse(
            nodes=[GraphNode(**n) for n in positioned_nodes],
            edges=[GraphEdge(**e) for e in edges],
            stats=GraphStats(
                nodes=len(positioned_nodes),
                edges=len(edges),
            ),
        )
        
    except Exception as e:
        logger.error(
            "Failed to get concept neighborhood",
            user_id=user.id,
            concept_id=concept_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get neighborhood: {str(e)}",
        )


# =============================================================================
# LEGACY NEIGHBORHOOD ENDPOINT
# =============================================================================


@router.get(
    "/neighborhood",
    summary="Get concept neighborhood or JIT tree for root",
    description="Get a concept neighborhood or full JIT tree for Poincare disk visualization.",
)
async def get_neighborhood(
    concept_label: Optional[str] = Query(None, description="Label of the concept (omit for root tree)"),
    rel_types: Optional[str] = Query(None, description="Comma-separated relationship types to include (e.g. isA,partOf)"),
    source_filter: Optional[str] = Query(None, description="Filter by source title (substring match)"),
    min_importance: Optional[float] = Query(None, ge=0, description="Minimum importance score"),
    user_id: Optional[str] = Query(None, description="User ID (deprecated: use JWT)"),
    user: Optional[User] = Depends(get_current_user_optional),
    graph_manager: GraphManager = Depends(get_graph_manager),
):
    """
    Get graph neighborhood for a concept by label, or JIT tree for root view.
    
    If concept_label is provided: returns NeighborhoodResponse with concept details.
    If concept_label is omitted: returns JITTreeNode with full nested tree for Poincare disk.
    
    Supports filtering by:
    - rel_types: comma-separated relationship types (isA, partOf, prerequisiteFor, relatedTo, oppositeOf, usedIn)
    - source_filter: substring match on source title
    - min_importance: minimum importance score for concepts
    """
    effective_user_id = user.id if user else user_id
    if not effective_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )

    # Parse filter parameters
    filters = {}
    if rel_types:
        filters["rel_types"] = [rt.strip() for rt in rel_types.split(",") if rt.strip()]
    if source_filter:
        filters["source_filter"] = source_filter
    if min_importance is not None:
        filters["min_importance"] = min_importance

    try:
        logger.info(
            "Fetching graph neighborhood",
            user_id=effective_user_id,
            concept_label=concept_label,
            filters=filters,
        )
        
        data = await graph_manager.get_concept_neighborhood(
            user_id=effective_user_id,
            concept_label=concept_label,
            filters=filters if filters else None,
        )
        
        if not data:
            # Return empty tree for root, empty neighborhood for concept
            if concept_label is None:
                return {
                    "id": f"synaptiq:root:{effective_user_id}",
                    "name": "Knowledge Graph",
                    "data": {"relation": "root", "$color": "#1A1A1A", "$dim": 28},
                    "children": []
                }
            return {
                "found": False,
                "uri": "",
                "label": concept_label,
                "relationships": {}
            }

        # Root view returns JIT tree, concept view returns neighborhood
        # Check if it's a JIT tree format (has 'id' and 'children' keys)
        if "id" in data and "children" in data and "name" in data:
            # JIT tree format - return as-is
            return data
        else:
            # Neighborhood format - return as NeighborhoodResponse
            return data
        
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


# =============================================================================
# EXPORT ENDPOINT
# =============================================================================


@router.get(
    "/export",
    summary="Export graph",
    responses={
        200: {
            "description": "Graph data in requested format",
            "content": {
                "text/turtle": {},
                "application/ld+json": {},
            },
        },
    },
)
async def export_graph(
    user: User = Depends(get_current_user),
    graph_manager: GraphManager = Depends(get_graph_manager),
    format: str = Query(default="turtle", description="Export format: turtle, json-ld"),
):
    """
    Export the user's knowledge graph.
    
    Supported formats:
    - turtle: Turtle/N3 format
    - json-ld: JSON-LD format
    
    Requires JWT authentication.
    """
    try:
        graph_data = await graph_manager.export_graph(user.id, format=format)
        
        content_type = {
            "turtle": "text/turtle",
            "json-ld": "application/ld+json",
        }.get(format, "text/turtle")
        
        from fastapi.responses import Response
        return Response(
            content=graph_data,
            media_type=content_type,
        )
        
    except Exception as e:
        logger.error("Graph export failed", user_id=user.id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Export failed: {str(e)}",
        )


# =============================================================================
# CONSOLIDATION ENDPOINT
# =============================================================================


class ConsolidationResponse(BaseModel):
    """Response from graph consolidation."""
    
    duplicates_merged: int = Field(default=0)
    orphans_removed: int = Field(default=0)
    weak_rels_removed: int = Field(default=0)


@router.post(
    "/consolidate",
    response_model=ConsolidationResponse,
    summary="Run graph consolidation",
    description="Merge duplicates, remove orphans, and clean up weak relationships.",
)
async def consolidate_graph(
    user: User = Depends(get_current_user),
    graph_manager: GraphManager = Depends(get_graph_manager),
) -> ConsolidationResponse:
    """
    Run post-ingestion consolidation on the user's knowledge graph.
    
    This merges duplicate concepts, removes orphans (no relationships,
    single mention, no definition), and removes weak relatedTo edges
    between low-importance concepts.
    
    Requires JWT authentication.
    """
    try:
        from synaptiq.services.graph_consolidation import GraphConsolidationService
        
        service = GraphConsolidationService(fuseki_store=graph_manager.fuseki)
        summary = await service.consolidate(user.id)
        
        return ConsolidationResponse(**summary)
        
    except Exception as e:
        logger.error("Graph consolidation failed", user_id=user.id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Consolidation failed: {str(e)}",
        )
