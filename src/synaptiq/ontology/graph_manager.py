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
        # get_graph_stats now includes all counts (concepts, chunks, sources,
        # definitions, relationships) computed in parallel
        stats = await self.fuseki.get_graph_stats(user_id)
        
        # Add graph URI
        stats["graph_uri"] = build_user_graph_uri(user_id)
        
        return stats

    # ═══════════════════════════════════════════════════════════════════════════════
    # GRAPH TRAVERSAL
    # ═══════════════════════════════════════════════════════════════════════════════

    async def _get_root_concepts(self, user_id: str) -> dict[str, Any]:
        """
        Build a deeply nested tree structure for JIT Hypertree visualization.
        
        Returns a tree with structure matching JIT requirements:
        {
            "id": "root",
            "name": "Knowledge Graph",
            "data": {...},
            "children": [
                {
                    "id": "concept1",
                    "name": "Concept 1",
                    "data": {...},
                    "children": [
                        { "id": "...", "name": "Related", "data": {...}, "children": [] }
                    ]
                }
            ]
        }
        """
        # Get all concepts with their relationships in one query
        # Include BOTH outgoing and incoming relationships so concepts appear
        # under all related parents (bidirectional visibility for interconnection)
        # Also fetch source information for provenance
        sparql = """
        SELECT ?concept ?label ?relType ?relatedConcept ?relatedLabel ?direction ?sourceTitle
        WHERE {
            ?concept a syn:Concept ;
                     syn:label ?label .
            OPTIONAL {
                # Get source info for this concept
                ?concept syn:definedIn ?chunk .
                ?chunk syn:derivedFrom ?source .
                ?source syn:sourceTitle ?sourceTitle .
            }
            OPTIONAL {
                {
                    # Outgoing: this concept relates TO another
                    ?concept ?relType ?relatedConcept .
                    ?relatedConcept a syn:Concept ;
                                    syn:label ?relatedLabel .
                    BIND("outgoing" AS ?direction)
                    FILTER(?relType IN (
                        syn:isA, syn:partOf, syn:prerequisiteFor, 
                        syn:relatedTo, syn:oppositeOf, syn:usedIn
                    ))
                }
                UNION
                {
                    # Incoming: another concept relates TO this concept
                    ?relatedConcept ?relType ?concept .
                    ?relatedConcept a syn:Concept ;
                                    syn:label ?relatedLabel .
                    BIND("incoming" AS ?direction)
                    FILTER(?relType IN (
                        syn:isA, syn:partOf, syn:prerequisiteFor, 
                        syn:relatedTo, syn:oppositeOf, syn:usedIn
                    ))
                }
            }
        }
        ORDER BY ?label
        """
        
        try:
            results = await self.fuseki.query(user_id, sparql)
            
            # Build concept -> relationships mapping
            concept_map: dict[str, dict] = {}
            
            for r in results:
                label = r.get("label", "")
                if not label:
                    continue
                
                concept_uri = r.get("concept", "")
                direction = r.get("direction", "outgoing")
                source_title = r.get("sourceTitle", "")
                
                if label not in concept_map:
                    concept_map[label] = {
                        "uri": concept_uri,
                        "label": label,
                        "sourceTitle": source_title,  # Store source for provenance
                        "children": {}  # (relType, direction) -> list of related labels
                    }
                elif source_title and not concept_map[label].get("sourceTitle"):
                    # Update if we didn't have a source before
                    concept_map[label]["sourceTitle"] = source_title
                
                rel_type = r.get("relType", "").split("#")[-1]
                related_label = r.get("relatedLabel", "")
                
                if rel_type and related_label:
                    # Use a key that includes direction to preserve both relationships
                    rel_key = (rel_type, direction)
                    if rel_key not in concept_map[label]["children"]:
                        concept_map[label]["children"][rel_key] = []
                    if related_label not in concept_map[label]["children"][rel_key]:
                        concept_map[label]["children"][rel_key].append(related_label)
            
            # Relationship type labels - outgoing direction
            REL_LABELS_OUT = {
                "isA": "is a",
                "partOf": "part of",
                "prerequisiteFor": "prerequisite for",
                "relatedTo": "related to",
                "oppositeOf": "opposite of",
                "usedIn": "used in",
            }
            
            # Inverse labels for incoming direction (from the perspective of this concept)
            REL_LABELS_IN = {
                "isA": "has type",
                "partOf": "contains",
                "prerequisiteFor": "requires",
                "relatedTo": "related to",  # symmetric
                "oppositeOf": "opposite of",  # symmetric
                "usedIn": "uses",
            }
            
            # Build JIT tree structure: Root -> Concepts -> Related Concepts
            # DEDUPLICATION: Don't show a concept as both parent AND child
            
            # Step 1: Collect all concepts that appear as children
            child_concepts = set()
            for concept_label, concept_data in concept_map.items():
                for rel_key, related_labels in concept_data["children"].items():
                    for related_label in related_labels:
                        child_concepts.add(related_label.lower())
            
            # Step 2: Score concepts by how many relationships they have
            concept_scores = {}
            for concept_label, concept_data in concept_map.items():
                child_count = sum(len(labels) for labels in concept_data["children"].values())
                # Bonus for concepts that are NOT children elsewhere (more unique as parents)
                is_primarily_child = concept_label.lower() in child_concepts and child_count < 2
                concept_scores[concept_label] = (
                    0 if is_primarily_child else child_count,  # Deprioritize if primarily a child
                    child_count,  # Secondary sort by total connections
                )
            
            # Step 3: Sort by score (most connected first) and filter
            sorted_concepts = sorted(
                concept_map.keys(),
                key=lambda c: concept_scores.get(c, (0, 0)),
                reverse=True
            )
            
            jit_children = []
            shown_as_parent = set()
            
            for concept_label in sorted_concepts[:60]:  # Increased limit
                concept_data = concept_map[concept_label]
                
                # Skip if this concept has no children and appears as a child elsewhere
                child_count = sum(len(labels) for labels in concept_data["children"].values())
                if child_count == 0 and concept_label.lower() in child_concepts:
                    continue  # This concept is only shown as a child of others
                
                # Build grandchildren (related concepts)
                grandchildren = []
                for rel_key, related_labels in concept_data["children"].items():
                    rel_type, direction = rel_key
                    
                    # Select the appropriate label based on direction
                    if direction == "incoming":
                        rel_label = REL_LABELS_IN.get(rel_type, rel_type)
                    else:
                        rel_label = REL_LABELS_OUT.get(rel_type, rel_type)
                    
                    for related_label in related_labels[:10]:
                        # Look up source for this related concept
                        related_source = concept_map.get(related_label, {}).get("sourceTitle", "")
                        grandchildren.append({
                            "id": f"{concept_label}#{direction}#{rel_type}#{related_label}".replace(" ", "_"),
                            "name": related_label,
                            "data": {
                                "relation": rel_label,
                                "sourceTitle": related_source,  # Where this concept came from
                                "$color": "#0066CC",
                                "$dim": 10,
                            },
                            "children": []
                        })
                
                # Only add as parent if has children
                if grandchildren:
                    jit_children.append({
                        "id": f"concept_{concept_label}".replace(" ", "_"),
                        "name": concept_label,
                        "data": {
                            "relation": "concept",
                            "sourceTitle": concept_data.get("sourceTitle", ""),  # Parent's source
                            "$color": "#0066CC",
                            "$dim": 14,
                        },
                        "children": grandchildren
                    })
                    shown_as_parent.add(concept_label.lower())
            
            # Build adjacencies list for cross-node connections
            # Connect nodes that represent the same concept under different parents
            adjacencies = []
            
            # Build a map: related_label -> list of node IDs that reference it
            label_to_node_ids: dict[str, list[str]] = {}
            for child in jit_children:
                concept_label = child.get("name", "")
                for grandchild in child.get("children", []):
                    related_label = grandchild.get("name", "").lower()
                    node_id = grandchild.get("id", "")
                    if related_label and node_id:
                        if related_label not in label_to_node_ids:
                            label_to_node_ids[related_label] = []
                        label_to_node_ids[related_label].append(node_id)
            
            # For each label that appears multiple times, create adjacencies between its nodes
            for label, node_ids in label_to_node_ids.items():
                if len(node_ids) > 1:
                    # Connect first occurrence to all others
                    first_id = node_ids[0]
                    for other_id in node_ids[1:]:
                        adjacencies.append({
                            "nodeFrom": first_id,
                            "nodeTo": other_id,
                            "data": {"$color": "#88CC00", "$lineWidth": 1}
                        })
            
            # Also connect concepts that have explicit relationships with each other
            # (parent-level concepts that are related)
            for i, child1 in enumerate(jit_children):
                name1 = child1.get("name", "").lower()
                for grandchild in child1.get("children", []):
                    related_name = grandchild.get("name", "").lower()
                    # Check if related_name is also a parent concept
                    for child2 in jit_children:
                        name2 = child2.get("name", "").lower()
                        if name2 == related_name and name1 != name2:
                            # Create adjacency from parent1 to parent2
                            adjacencies.append({
                                "nodeFrom": child1.get("id", ""),
                                "nodeTo": child2.get("id", ""),
                                "data": {"$color": "#00AAFF", "$lineWidth": 2}
                            })
            
            # Return JIT-compatible nested tree WITH adjacencies
            return {
                "id": f"synaptiq:root:{user_id}",
                "name": "Knowledge Graph",
                "data": {
                    "relation": "root",
                    "$color": "#1A1A1A",
                    "$dim": 28,
                },
                "children": jit_children,
                "adjacencies": adjacencies  # NEW: cross-node connections
            }
            
        except Exception as e:
            logger.warning("Failed to get root concepts", user_id=user_id, error=str(e))
            return {
                "id": f"synaptiq:root:{user_id}",
                "name": "Knowledge Graph",
                "data": {"relation": "root", "$color": "#1A1A1A", "$dim": 28},
                "children": [{
                    "id": "empty",
                    "name": "Ingest content to build your graph",
                    "data": {"$color": "#666666", "$dim": 10},
                    "children": []
                }]
            }

    async def get_concept_neighborhood(
        self,
        user_id: str,
        concept_label: Optional[str] = None,
        depth: int = 1,
    ) -> dict[str, Any]:
        """
        Get a concept and its immediate neighborhood.
        
        Args:
            user_id: User identifier
            concept_label: Concept label to explore (None returns top-level concepts)
            depth: How many hops to traverse (1 = direct relations only)
            
        Returns:
            Dict with concept details, definitions, and relationships
        """
        # If no concept specified, return root/top-level concepts
        if not concept_label:
            return await self._get_root_concepts(user_id)
        
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
            logger.info("Concept not found", concept_label=concept_label, user_id=user_id)
            return {"found": False, "label": concept_label, "uri": "", "relationships": {}}
        
        concept_uri = results[0].get("concept")
        logger.info("Found concept", concept_label=concept_label, concept_uri=concept_uri)
        
        # Get concept details
        details = await self.fuseki.get_concept_with_definition(user_id, concept_uri)
        
        # Get relationships
        relationships = await self.fuseki.get_concept_relationships(user_id, concept_uri)
        logger.info(
            "Fetched relationships",
            concept_label=concept_label,
            relationship_count=len(relationships),
            relationships=relationships[:5] if relationships else [],  # Log first 5
        )
        
        # Organize by relationship type
        outgoing: dict[str, list[str]] = {}
        rich_outgoing: dict[str, list[dict]] = {}
        
        for rel in relationships:
            rel_type = rel.get("relationType", "").split("#")[-1]
            related_label = rel.get("relatedLabel", "")
            related_uri = rel.get("relatedConcept", "")
            
            # Determine direction by checking if this concept is subject or object
            # This is a simplification; proper implementation would check actual direction
            if rel_type and related_label:
                if rel_type not in outgoing:
                    outgoing[rel_type] = []
                    rich_outgoing[rel_type] = []
                outgoing[rel_type].append(related_label)
                rich_outgoing[rel_type].append({
                    "uri": related_uri,
                    "label": related_label,
                    "nodeType": "instance",
                    "entityType": "concept",
                })
        
        return {
            "found": True,
            "uri": concept_uri,
            "label": details.get("label") if details else concept_label,
            "nodeType": "instance",
            "entityType": "concept",
            "sourceType": None,
            "definition": details.get("definitionText") if details else None,
            "source": {
                "title": details.get("sourceTitle") if details else None,
                "url": details.get("sourceUrl") if details else None,
            },
            "relationships": outgoing,
            "richRelationships": rich_outgoing,
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

