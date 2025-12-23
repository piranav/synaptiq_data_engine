"""
Function tools for agent retrieval.

These tools are used by agents to query the knowledge graph and vector store.
"""

from typing import Optional, Any
import structlog

from agents import function_tool, RunContextWrapper

from .context import AgentContext
from .schemas import VectorSearchResult, GraphSearchResult, SparqlQueryResult

logger = structlog.get_logger(__name__)


@function_tool
async def vector_search(
    ctx: RunContextWrapper[AgentContext],
    query: str,
    top_k: int = 5,
    source_type: Optional[str] = None,
    has_definition: Optional[bool] = None,
) -> list[dict[str, Any]]:
    """
    Search the vector store for semantically similar content.
    
    Args:
        query: The search query text
        top_k: Maximum number of results to return (default: 5)
        source_type: Filter by source type (youtube, web_article, note)
        has_definition: Filter for chunks containing definitions
        
    Returns:
        List of matching chunks with text, score, and source metadata
    """
    agent_ctx = ctx.context
    
    logger.info(
        "Vector search",
        query=query[:50],
        user_id=agent_ctx.user_id,
        top_k=top_k,
        source_type=source_type,
    )
    
    try:
        # Generate query embedding
        query_vector = await agent_ctx.embedding_generator.generate_single(query)
        
        # Search with user isolation
        results = await agent_ctx.qdrant_store.search(
            query_vector=query_vector,
            user_id=agent_ctx.user_id,
            limit=top_k,
            source_type=source_type,
            has_definition=has_definition,
        )
        
        # Format results
        formatted = []
        for r in results:
            payload = r.get("payload", {})
            formatted.append({
                "chunk_id": r["id"],
                "text": payload.get("text", ""),
                "score": r["score"],
                "source_title": payload.get("source_title"),
                "source_url": payload.get("source_url"),
                "source_type": payload.get("source_type"),
                "timestamp_start": payload.get("timestamp_start"),
            })
        
        logger.info("Vector search complete", result_count=len(formatted))
        return formatted
        
    except Exception as e:
        logger.error("Vector search failed", error=str(e))
        return []


@function_tool
async def execute_sparql(
    ctx: RunContextWrapper[AgentContext],
    sparql_query: str,
) -> dict[str, Any]:
    """
    Execute a SPARQL query against the user's knowledge graph.
    
    The query should use {USER_ID} as a placeholder for the user's graph URI.
    This placeholder will be replaced at execution time.
    
    Args:
        sparql_query: The SPARQL SELECT query to execute
        
    Returns:
        Query results with success status and any errors
    """
    agent_ctx = ctx.context
    
    # Replace placeholder with actual user_id
    query = sparql_query.replace("{USER_ID}", agent_ctx.user_id)
    
    logger.info(
        "Execute SPARQL",
        user_id=agent_ctx.user_id,
        query_preview=query[:100],
    )
    
    try:
        results = await agent_ctx.fuseki_store.query(
            user_id=agent_ctx.user_id,
            sparql=query,
            include_ontology=True,
        )
        
        logger.info("SPARQL query complete", result_count=len(results))
        
        return {
            "query": query,
            "results": results,
            "success": True,
            "error": None,
        }
        
    except Exception as e:
        logger.error("SPARQL query failed", error=str(e))
        return {
            "query": query,
            "results": [],
            "success": False,
            "error": str(e),
        }


@function_tool
async def get_concept_details(
    ctx: RunContextWrapper[AgentContext],
    concept_label: str,
) -> Optional[dict[str, Any]]:
    """
    Get detailed information about a specific concept from the knowledge graph.
    
    Args:
        concept_label: The label of the concept to look up
        
    Returns:
        Concept details including definition and relationships, or None if not found
    """
    agent_ctx = ctx.context
    
    logger.info(
        "Get concept details",
        concept_label=concept_label,
        user_id=agent_ctx.user_id,
    )
    
    try:
        # First find the concept URI
        concept_uri = await agent_ctx.fuseki_store.concept_exists(
            agent_ctx.user_id,
            concept_label,
        )
        
        if not concept_uri:
            logger.info("Concept not found", concept_label=concept_label)
            return None
        
        # Get concept with definition
        details = await agent_ctx.fuseki_store.get_concept_with_definition(
            agent_ctx.user_id,
            concept_uri,
        )
        
        # Get relationships
        relationships = await agent_ctx.fuseki_store.get_concept_relationships(
            agent_ctx.user_id,
            concept_uri,
        )
        
        return {
            "uri": concept_uri,
            "label": concept_label,
            "details": details,
            "relationships": relationships,
        }
        
    except Exception as e:
        logger.error("Get concept details failed", error=str(e))
        return None


@function_tool
async def find_concept_path(
    ctx: RunContextWrapper[AgentContext],
    concept_a: str,
    concept_b: str,
    max_depth: int = 3,
) -> list[dict[str, Any]]:
    """
    Find relationship paths between two concepts in the knowledge graph.
    
    Args:
        concept_a: First concept label
        concept_b: Second concept label
        max_depth: Maximum path length to search (default: 3)
        
    Returns:
        List of paths connecting the concepts
    """
    agent_ctx = ctx.context
    
    logger.info(
        "Find concept path",
        concept_a=concept_a,
        concept_b=concept_b,
        user_id=agent_ctx.user_id,
    )
    
    try:
        # Build path-finding SPARQL
        # This finds direct and one-hop indirect relationships
        sparql = f"""
        SELECT ?relation ?intermediate ?relation2
        WHERE {{
            {{
                # Direct relationship
                ?conceptA syn:label "{concept_a.lower()}" .
                ?conceptB syn:label "{concept_b.lower()}" .
                ?conceptA ?relation ?conceptB .
                FILTER(?relation IN (
                    syn:isA, syn:partOf, syn:prerequisiteFor,
                    syn:relatedTo, syn:oppositeOf, syn:usedIn
                ))
                BIND("direct" AS ?intermediate)
                BIND(?relation AS ?relation2)
            }} UNION {{
                # One-hop indirect relationship
                ?conceptA syn:label "{concept_a.lower()}" .
                ?conceptB syn:label "{concept_b.lower()}" .
                ?conceptA ?relation ?intermediateNode .
                ?intermediateNode a syn:Concept .
                ?intermediateNode syn:label ?intermediate .
                ?intermediateNode ?relation2 ?conceptB .
                FILTER(?relation IN (
                    syn:isA, syn:partOf, syn:prerequisiteFor,
                    syn:relatedTo, syn:oppositeOf, syn:usedIn
                ))
                FILTER(?relation2 IN (
                    syn:isA, syn:partOf, syn:prerequisiteFor,
                    syn:relatedTo, syn:oppositeOf, syn:usedIn
                ))
            }}
        }}
        LIMIT 10
        """
        
        results = await agent_ctx.fuseki_store.query(
            user_id=agent_ctx.user_id,
            sparql=sparql,
        )
        
        logger.info("Find concept path complete", result_count=len(results))
        return results
        
    except Exception as e:
        logger.error("Find concept path failed", error=str(e))
        return []


@function_tool
async def get_concepts_from_source(
    ctx: RunContextWrapper[AgentContext],
    source_name: str,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """
    Get all concepts learned from a specific source.
    
    Args:
        source_name: Part of the source title to search for
        limit: Maximum number of concepts to return
        
    Returns:
        List of concepts with their definitions from this source
    """
    agent_ctx = ctx.context
    
    logger.info(
        "Get concepts from source",
        source_name=source_name,
        user_id=agent_ctx.user_id,
    )
    
    try:
        sparql = f"""
        SELECT DISTINCT ?conceptLabel ?definitionText ?sourceTitle ?sourceUrl
        WHERE {{
            ?source syn:sourceTitle ?sourceTitle .
            FILTER(CONTAINS(LCASE(?sourceTitle), "{source_name.lower()}"))
            ?chunk syn:derivedFrom ?source .
            ?concept syn:definedIn|syn:mentionedIn ?chunk .
            ?concept syn:label ?conceptLabel .
            OPTIONAL {{
                ?concept syn:hasDefinition ?def .
                ?def syn:definitionText ?definitionText .
            }}
            OPTIONAL {{ ?source syn:sourceUrl ?sourceUrl }}
        }}
        LIMIT {limit}
        """
        
        results = await agent_ctx.fuseki_store.query(
            user_id=agent_ctx.user_id,
            sparql=sparql,
        )
        
        logger.info("Get concepts from source complete", result_count=len(results))
        return results
        
    except Exception as e:
        logger.error("Get concepts from source failed", error=str(e))
        return []


@function_tool
async def find_similar_concepts(
    ctx: RunContextWrapper[AgentContext],
    label: str,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """
    Find concepts with similar labels in the knowledge graph.
    
    Args:
        label: Label to search for (partial match)
        limit: Maximum results to return
        
    Returns:
        List of similar concepts with their labels and URIs
    """
    agent_ctx = ctx.context
    
    try:
        results = await agent_ctx.fuseki_store.find_similar_concepts(
            user_id=agent_ctx.user_id,
            label=label,
            limit=limit,
        )
        
        return results
        
    except Exception as e:
        logger.error("Find similar concepts failed", error=str(e))
        return []
