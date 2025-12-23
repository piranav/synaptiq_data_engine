"""
Graph manager for high-level operations on user knowledge graphs.

Provides user lifecycle management, export/import, and graph traversal
utilities for the knowledge graph.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional

import structlog

from synaptiq.ontology.namespaces import (
    SYNAPTIQ,
    build_ontology_graph_uri,
    build_user_graph_uri,
    get_sparql_prefixes,
)

if TYPE_CHECKING:
    from synaptiq.storage.fuseki import FusekiStore

logger = structlog.get_logger(__name__)


class GraphManager:
    """
    High-level operations for user knowledge graphs.
    
    Provides:
    - User lifecycle (create/delete graph)
    - Export/import in various formats
    - Graph traversal and analysis
    - Learning path computation
    """

    def __init__(
        self,
        fuseki_store: Optional[FusekiStore] = None,
    ):
        """
        Initialize the graph manager.
        
        Args:
            fuseki_store: FusekiStore instance (lazy initialized if None)
        """
        self._fuseki: Optional[FusekiStore] = fuseki_store
        
        logger.info("GraphManager initialized")

    @property
    def fuseki(self) -> FusekiStore:
        """Lazy-initialize FusekiStore."""
        if self._fuseki is None:
            from synaptiq.storage.fuseki import FusekiStore
            self._fuseki = FusekiStore()
        return self._fuseki

    def set_fuseki_store(self, fuseki_store: FusekiStore) -> None:
        """Set the Fuseki store instance."""
        self._fuseki = fuseki_store

    # ═══════════════════════════════════════════════════════════════════════════════
    # USER LIFECYCLE
    # ═══════════════════════════════════════════════════════════════════════════════

    async def onboard_user(self, user_id: str) -> str:
        """
        Create a named graph for a new user.
        
        Initializes the graph with ontology imports and metadata.
        
        Args:
            user_id: User identifier
            
        Returns:
            The created graph URI
        """
        await self.fuseki.ensure_dataset()
        
        if await self.fuseki.user_graph_exists(user_id):
            logger.info("User graph already exists", user_id=user_id)
            return build_user_graph_uri(user_id)
        
        graph_uri = await self.fuseki.create_user_graph(user_id)
        logger.info("User onboarded", user_id=user_id, graph_uri=graph_uri)
        return graph_uri

    async def delete_user_data(self, user_id: str) -> None:
        """
        Delete all user data (GDPR compliance).
        
        Drops the user's named graph entirely.
        
        Args:
            user_id: User identifier
        """
        await self.fuseki.drop_user_graph(user_id)
        logger.info("User data deleted", user_id=user_id)

    async def user_exists(self, user_id: str) -> bool:
        """
        Check if a user's graph exists.
        
        Args:
            user_id: User identifier
            
        Returns:
            True if user graph exists
        """
        return await self.fuseki.user_graph_exists(user_id)

    # ═══════════════════════════════════════════════════════════════════════════════
    # EXPORT / IMPORT
    # ═══════════════════════════════════════════════════════════════════════════════

    async def export_graph(
        self,
        user_id: str,
        format: str = "turtle",
    ) -> str:
        """
        Export a user's graph in the specified format.
        
        Args:
            user_id: User identifier
            format: Output format (turtle, json-ld, ntriples)
            
        Returns:
            Serialized graph data
        """
        graph_uri = build_user_graph_uri(user_id)
        
        # Use CONSTRUCT to get all triples
        sparql = f"""
        CONSTRUCT {{ ?s ?p ?o }}
        WHERE {{
            GRAPH <{graph_uri}> {{
                ?s ?p ?o
            }}
        }}
        """
        
        # Request appropriate content type
        content_type_map = {
            "turtle": "text/turtle",
            "json-ld": "application/ld+json",
            "ntriples": "application/n-triples",
            "rdf-xml": "application/rdf+xml",
        }
        
        accept = content_type_map.get(format.lower(), "text/turtle")
        
        # Execute via raw query with specific accept header
        import httpx
        
        async with httpx.AsyncClient(
            auth=(self.fuseki.admin_user, self.fuseki.admin_password),
            timeout=60.0,
        ) as client:
            response = await client.post(
                self.fuseki.query_endpoint,
                data={"query": sparql},
                headers={"Accept": accept},
            )
            
            if response.status_code == 200:
                return response.text
            else:
                logger.error(
                    "Export failed",
                    status=response.status_code,
                    response=response.text[:200],
                )
                return ""

    async def get_graph_statistics(self, user_id: str) -> dict[str, Any]:
        """
        Get detailed statistics for a user's graph.
        
        Args:
            user_id: User identifier
            
        Returns:
            Dict with concept count, relationships, sources, etc.
        """
        stats = await self.fuseki.get_graph_stats(user_id)
        
        # Add additional stats
        stats["graph_uri"] = build_user_graph_uri(user_id)
        
        # Get relationship counts by type
        rel_sparql = """
        SELECT ?relType (COUNT(*) AS ?count)
        WHERE {
            ?s ?relType ?o .
            ?s a syn:Concept .
            ?o a syn:Concept .
            FILTER(?relType IN (
                syn:isA, syn:partOf, syn:prerequisiteFor, 
                syn:relatedTo, syn:oppositeOf, syn:usedIn
            ))
        }
        GROUP BY ?relType
        """
        
        try:
            rel_results = await self.fuseki.query(user_id, rel_sparql)
            stats["relationships_by_type"] = {
                r.get("relType", "").split("#")[-1]: int(r.get("count", 0))
                for r in rel_results
            }
        except Exception as e:
            logger.warning("Failed to get relationship stats", error=str(e))
            stats["relationships_by_type"] = {}
        
        return stats

    # ═══════════════════════════════════════════════════════════════════════════════
    # GRAPH TRAVERSAL
    # ═══════════════════════════════════════════════════════════════════════════════

    async def get_concept_neighborhood(
        self,
        user_id: str,
        concept_label: str,
        depth: int = 1,
    ) -> dict[str, Any]:
        """
        Get a concept and its immediate neighborhood.
        
        Args:
            user_id: User identifier
            concept_label: Concept label to explore
            depth: How many hops to traverse (1 = direct relations only)
            
        Returns:
            Dict with concept details, definitions, and relationships
        """
        # First find the concept
        find_concept_sparql = f"""
        SELECT ?concept ?label ?altLabel
        WHERE {{
            ?concept a syn:Concept ;
                     syn:label ?label .
            OPTIONAL {{ ?concept syn:altLabel ?altLabel }}
            FILTER(LCASE(?label) = "{concept_label.lower()}")
        }}
        LIMIT 1
        """
        
        results = await self.fuseki.query(user_id, find_concept_sparql)
        if not results:
            return {"found": False, "label": concept_label}
        
        concept_uri = results[0].get("concept")
        
        # Get concept details
        details = await self.fuseki.get_concept_with_definition(user_id, concept_uri)
        
        # Get relationships
        relationships = await self.fuseki.get_concept_relationships(user_id, concept_uri)
        
        # Organize by relationship type
        outgoing: dict[str, list[str]] = {}
        incoming: dict[str, list[str]] = {}
        
        for rel in relationships:
            rel_type = rel.get("relationType", "").split("#")[-1]
            related_label = rel.get("relatedLabel", "")
            related_uri = rel.get("relatedConcept", "")
            
            # Determine direction by checking if this concept is subject or object
            # This is a simplification; proper implementation would check actual direction
            if rel_type:
                if rel_type not in outgoing:
                    outgoing[rel_type] = []
                outgoing[rel_type].append(related_label)
        
        return {
            "found": True,
            "uri": concept_uri,
            "label": details.get("label") if details else concept_label,
            "definition": details.get("definitionText") if details else None,
            "source": {
                "title": details.get("sourceTitle") if details else None,
                "url": details.get("sourceUrl") if details else None,
            },
            "relationships": outgoing,
        }

    async def find_learning_path(
        self,
        user_id: str,
        from_concept: str,
        to_concept: str,
        max_depth: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Find a learning path between two concepts using prerequisiteFor relationships.
        
        Args:
            user_id: User identifier
            from_concept: Starting concept label
            to_concept: Target concept label
            max_depth: Maximum path length to search
            
        Returns:
            List of concepts in the learning path
        """
        # Use property path to find path via prerequisiteFor
        sparql = f"""
        SELECT ?step ?stepLabel
        WHERE {{
            ?start syn:label "{from_concept.lower()}" .
            ?end syn:label "{to_concept.lower()}" .
            
            ?start syn:prerequisiteFor+ ?step .
            ?step syn:prerequisiteFor* ?end .
            ?step syn:label ?stepLabel .
        }}
        LIMIT 20
        """
        
        results = await self.fuseki.query(user_id, sparql)
        
        if not results:
            # Try reverse direction
            sparql_reverse = f"""
            SELECT ?step ?stepLabel
            WHERE {{
                ?start syn:label "{to_concept.lower()}" .
                ?end syn:label "{from_concept.lower()}" .
                
                ?end syn:prerequisiteFor+ ?step .
                ?step syn:prerequisiteFor* ?start .
                ?step syn:label ?stepLabel .
            }}
            LIMIT 20
            """
            results = await self.fuseki.query(user_id, sparql_reverse)
        
        path = [{"label": from_concept, "position": 0}]
        
        for i, r in enumerate(results):
            path.append({
                "label": r.get("stepLabel", ""),
                "uri": r.get("step", ""),
                "position": i + 1,
            })
        
        path.append({"label": to_concept, "position": len(path)})
        
        return path

    async def get_concepts_by_source(
        self,
        user_id: str,
        source_title_contains: str,
    ) -> list[dict[str, Any]]:
        """
        Get all concepts learned from a specific source.
        
        Args:
            user_id: User identifier
            source_title_contains: Substring to match in source title
            
        Returns:
            List of concepts with their definitions
        """
        sparql = f"""
        SELECT DISTINCT ?conceptLabel ?definitionText ?sourceTitle
        WHERE {{
            ?source syn:sourceTitle ?sourceTitle .
            FILTER(CONTAINS(LCASE(?sourceTitle), "{source_title_contains.lower()}"))
            
            ?chunk syn:derivedFrom ?source .
            
            {{
                ?concept syn:definedIn ?chunk .
            }} UNION {{
                ?concept syn:mentionedIn ?chunk .
            }}
            
            ?concept syn:label ?conceptLabel .
            
            OPTIONAL {{
                ?concept syn:hasDefinition ?def .
                ?def syn:definitionText ?definitionText .
            }}
        }}
        ORDER BY ?conceptLabel
        """
        
        return await self.fuseki.query(user_id, sparql)

    async def get_undefined_concepts(
        self,
        user_id: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """
        Get concepts that are mentioned but not defined.
        
        Useful for identifying knowledge gaps.
        
        Args:
            user_id: User identifier
            limit: Maximum results
            
        Returns:
            List of concepts without definitions
        """
        sparql = f"""
        SELECT ?concept ?label (COUNT(?mention) AS ?mentionCount)
        WHERE {{
            ?concept a syn:Concept ;
                     syn:label ?label .
            ?concept syn:mentionedIn ?mention .
            
            FILTER NOT EXISTS {{
                ?concept syn:hasDefinition ?def .
            }}
        }}
        GROUP BY ?concept ?label
        ORDER BY DESC(?mentionCount)
        LIMIT {limit}
        """
        
        return await self.fuseki.query(user_id, sparql)

    async def get_concept_timeline(
        self,
        user_id: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """
        Get concepts ordered by when they were first learned.
        
        Args:
            user_id: User identifier
            limit: Maximum results
            
        Returns:
            List of concepts with creation timestamps
        """
        sparql = f"""
        SELECT ?concept ?label ?createdAt ?sourceTitle
        WHERE {{
            ?concept a syn:Concept ;
                     syn:label ?label ;
                     syn:createdAt ?createdAt .
            
            OPTIONAL {{
                ?concept syn:firstLearnedFrom ?source .
                ?source syn:sourceTitle ?sourceTitle .
            }}
        }}
        ORDER BY ?createdAt
        LIMIT {limit}
        """
        
        return await self.fuseki.query(user_id, sparql)

    async def find_related_concepts(
        self,
        user_id: str,
        concept_label: str,
        relation_types: Optional[list[str]] = None,
    ) -> list[dict[str, Any]]:
        """
        Find concepts related to a given concept.
        
        Args:
            user_id: User identifier
            concept_label: Concept to find relations for
            relation_types: Optional filter for specific relation types
            
        Returns:
            List of related concepts with relationship types
        """
        if relation_types:
            type_filter = ", ".join(f"syn:{t}" for t in relation_types)
            filter_clause = f"FILTER(?relType IN ({type_filter}))"
        else:
            filter_clause = """
            FILTER(?relType IN (
                syn:isA, syn:partOf, syn:prerequisiteFor, 
                syn:relatedTo, syn:oppositeOf, syn:usedIn
            ))
            """
        
        sparql = f"""
        SELECT ?relatedConcept ?relatedLabel ?relationType
        WHERE {{
            ?concept syn:label "{concept_label.lower()}" .
            
            {{
                ?concept ?relType ?relatedConcept .
                BIND("outgoing" AS ?direction)
            }} UNION {{
                ?relatedConcept ?relType ?concept .
                BIND("incoming" AS ?direction)
            }}
            
            ?relatedConcept a syn:Concept ;
                           syn:label ?relatedLabel .
            
            {filter_clause}
            
            BIND(STRAFTER(STR(?relType), "#") AS ?relationType)
        }}
        ORDER BY ?relationType ?relatedLabel
        """
        
        return await self.fuseki.query(user_id, sparql)

    async def close(self) -> None:
        """Close the Fuseki connection."""
        if self._fuseki:
            await self._fuseki.close()

