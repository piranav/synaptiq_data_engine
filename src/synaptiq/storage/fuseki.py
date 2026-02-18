"""
Apache Fuseki SPARQL store for RDF graph storage.

Provides async SPARQL client with named graph support for multi-tenant
user knowledge graphs.
"""

import json
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urljoin

import httpx
import structlog

from config.settings import get_settings
from synaptiq.core.exceptions import StorageError
from synaptiq.ontology.namespaces import (
    SYNAPTIQ,
    RDF,
    build_ontology_graph_uri,
    build_user_graph_uri,
    get_sparql_prefixes,
)

logger = structlog.get_logger(__name__)


class FusekiStore:
    """
    Async SPARQL client for Apache Fuseki with named graph support.
    
    Features:
    - Named graph isolation per user
    - Automatic PREFIX injection
    - SPARQL UPDATE and QUERY support
    - Dataset management via Fuseki admin API
    """

    def __init__(
        self,
        url: Optional[str] = None,
        dataset: Optional[str] = None,
        admin_user: Optional[str] = None,
        admin_password: Optional[str] = None,
    ):
        """
        Initialize the Fuseki store.
        
        Args:
            url: Fuseki server URL (default from settings)
            dataset: Dataset name (default from settings)
            admin_user: Admin username (default from settings)
            admin_password: Admin password (default from settings)
        """
        settings = get_settings()
        self.url = (url or settings.fuseki_url).rstrip("/")
        self.dataset = dataset or settings.fuseki_dataset
        self.admin_user = admin_user or settings.fuseki_admin_user
        self.admin_password = admin_password or settings.fuseki_admin_password
        
        # Endpoints
        self.query_endpoint = f"{self.url}/{self.dataset}/query"
        self.update_endpoint = f"{self.url}/{self.dataset}/update"
        self.data_endpoint = f"{self.url}/{self.dataset}/data"
        self.admin_endpoint = f"{self.url}/$/datasets"
        
        # HTTP client with auth
        self.client = httpx.AsyncClient(
            auth=(self.admin_user, self.admin_password),
            timeout=30.0,
        )
        
        logger.info(
            "FusekiStore initialized",
            url=self.url,
            dataset=self.dataset,
        )

    async def ensure_dataset(self) -> None:
        """
        Ensure the dataset exists, creating it if necessary.
        
        Uses Fuseki admin API to create a persistent TDB2 dataset.
        """
        try:
            # Check if dataset exists
            response = await self.client.get(self.admin_endpoint)
            
            if response.status_code == 200:
                datasets = response.json().get("datasets", [])
                dataset_names = [d.get("ds.name", "").lstrip("/") for d in datasets]
                
                if self.dataset in dataset_names:
                    logger.info("Dataset already exists", dataset=self.dataset)
                    return
            
            # Create dataset with TDB2 (persistent storage)
            create_response = await self.client.post(
                self.admin_endpoint,
                data={
                    "dbName": self.dataset,
                    "dbType": "tdb2",
                },
            )
            
            if create_response.status_code in (200, 201):
                logger.info("Dataset created", dataset=self.dataset)
                # Load ontology into shared graph
                await self._load_ontology()
            else:
                raise StorageError(
                    message=f"Failed to create dataset: {create_response.text}",
                    store_type="fuseki",
                    operation="ensure_dataset",
                )
                
        except httpx.RequestError as e:
            logger.error("Failed to connect to Fuseki", error=str(e))
            raise StorageError(
                message=f"Failed to connect to Fuseki: {str(e)}",
                store_type="fuseki",
                operation="ensure_dataset",
                cause=e,
            )

    async def _load_ontology(self) -> None:
        """Load the synaptiq ontology into the shared ontology graph."""
        try:
            # Find the ontology file
            ontology_path = Path(__file__).parent.parent / "ontology" / "synaptiq.ttl"
            
            if not ontology_path.exists():
                logger.warning("Ontology file not found", path=str(ontology_path))
                return
            
            ontology_content = ontology_path.read_text()
            ontology_graph_uri = build_ontology_graph_uri()
            
            # Upload to named graph
            response = await self.client.put(
                f"{self.data_endpoint}?graph={ontology_graph_uri}",
                content=ontology_content,
                headers={"Content-Type": "text/turtle"},
            )
            
            if response.status_code in (200, 201, 204):
                logger.info("Ontology loaded", graph=ontology_graph_uri)
            else:
                logger.warning(
                    "Failed to load ontology",
                    status=response.status_code,
                    response=response.text[:200],
                )
                
        except Exception as e:
            logger.error("Error loading ontology", error=str(e))

    async def create_user_graph(self, user_id: str) -> str:
        """
        Create a named graph for a user.
        
        Initializes the graph with owl:imports for the shared ontology.
        
        Args:
            user_id: User identifier
            
        Returns:
            The created graph URI
        """
        graph_uri = build_user_graph_uri(user_id)
        ontology_uri = build_ontology_graph_uri()
        
        # Initialize graph with ontology import
        sparql = f"""
        {get_sparql_prefixes()}
        
        INSERT DATA {{
            GRAPH <{graph_uri}> {{
                <{graph_uri}> owl:imports <{ontology_uri}> .
                <{graph_uri}> syn:userId "{user_id}" .
                <{graph_uri}> syn:createdAt "{self._now_iso()}"^^xsd:dateTime .
            }}
        }}
        """
        
        await self._execute_update(sparql)
        logger.info("User graph created", user_id=user_id, graph_uri=graph_uri)
        return graph_uri

    async def drop_user_graph(self, user_id: str) -> None:
        """
        Drop a user's named graph (GDPR deletion).
        
        Args:
            user_id: User identifier
        """
        graph_uri = build_user_graph_uri(user_id)
        
        sparql = f"DROP SILENT GRAPH <{graph_uri}>"
        await self._execute_update(sparql)
        logger.info("User graph dropped", user_id=user_id, graph_uri=graph_uri)

    async def user_graph_exists(self, user_id: str) -> bool:
        """
        Check if a user's graph exists.
        
        Args:
            user_id: User identifier
            
        Returns:
            True if graph exists
        """
        graph_uri = build_user_graph_uri(user_id)
        
        sparql = f"""
        ASK {{
            GRAPH <{graph_uri}> {{
                ?s ?p ?o
            }}
        }}
        """
        
        result = await self._execute_query(sparql, result_format="json")
        return result.get("boolean", False)

    async def insert_triples(
        self,
        user_id: str,
        triples: list[dict[str, Any]],
    ) -> int:
        """
        Insert triples into a user's graph.
        
        Args:
            user_id: User identifier
            triples: List of triple dicts with 'subject', 'predicate', 'object', 'is_literal'
            
        Returns:
            Number of triples inserted
        """
        if not triples:
            return 0
        
        graph_uri = build_user_graph_uri(user_id)
        
        # Build triple patterns
        triple_patterns = []
        for t in triples:
            obj = t["object"]
            if t.get("is_literal", False):
                # Handle literal values
                if isinstance(obj, str):
                    # Escape quotes in string
                    obj = obj.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
                    obj_str = f'"{obj}"'
                elif isinstance(obj, bool):
                    obj_str = f'"{str(obj).lower()}"^^xsd:boolean'
                elif isinstance(obj, int):
                    obj_str = f'"{obj}"^^xsd:integer'
                elif isinstance(obj, float):
                    obj_str = f'"{obj}"^^xsd:float'
                else:
                    obj_str = f'"{obj}"'
            else:
                # URI reference
                obj_str = f"<{obj}>"
            
            triple_patterns.append(f"<{t['subject']}> <{t['predicate']}> {obj_str} .")
        
        sparql = f"""
        {get_sparql_prefixes()}
        
        INSERT DATA {{
            GRAPH <{graph_uri}> {{
                {chr(10).join(triple_patterns)}
            }}
        }}
        """
        
        await self._execute_update(sparql)
        logger.debug("Inserted triples", user_id=user_id, count=len(triples))
        return len(triples)

    async def query(
        self,
        user_id: str,
        sparql: str,
        include_ontology: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Execute a SPARQL SELECT query scoped to a user's graph.
        
        Automatically injects FROM clauses for user isolation.
        
        Args:
            user_id: User identifier
            sparql: SPARQL SELECT query (without FROM clause)
            include_ontology: Whether to include ontology graph for inference
            
        Returns:
            List of result bindings
        """
        graph_uri = build_user_graph_uri(user_id)
        ontology_uri = build_ontology_graph_uri()
        
        # Build FROM clauses
        from_clauses = f"FROM <{graph_uri}>"
        if include_ontology:
            from_clauses += f"\nFROM <{ontology_uri}>"
        
        # Build full query with prefixes
        full_sparql = f"{get_sparql_prefixes()}\n{sparql}"
        
        # Insert FROM clauses AFTER SELECT/CONSTRUCT/etc. and BEFORE WHERE
        # SPARQL structure: PREFIX... SELECT... FROM... WHERE...
        import re
        
        # Pattern to find SELECT/CONSTRUCT/ASK/DESCRIBE with optional variables/expressions
        # and insert FROM before WHERE
        where_pattern = r"(WHERE\s*\{)"
        full_sparql = re.sub(
            where_pattern,
            f"{from_clauses}\n\\1",
            full_sparql,
            count=1,
            flags=re.IGNORECASE,
        )
        
        result = await self._execute_query(full_sparql, result_format="json")
        
        # Extract bindings
        bindings = result.get("results", {}).get("bindings", [])
        return [
            {
                var: binding[var].get("value")
                for var in binding
            }
            for binding in bindings
        ]

    async def query_raw(self, sparql: str) -> list[dict[str, Any]]:
        """
        Execute a raw SPARQL query without user scoping.
        
        Use with caution - bypasses user isolation.
        
        Args:
            sparql: Full SPARQL query
            
        Returns:
            List of result bindings
        """
        full_sparql = f"{get_sparql_prefixes()}\n{sparql}"
        result = await self._execute_query(full_sparql, result_format="json")
        
        bindings = result.get("results", {}).get("bindings", [])
        return [
            {
                var: binding[var].get("value")
                for var in binding
            }
            for binding in bindings
        ]

    async def concept_exists(
        self,
        user_id: str,
        label: str,
    ) -> Optional[str]:
        """
        Check if a concept with the given label exists in user's graph.
        
        Args:
            user_id: User identifier
            label: Concept label to search for
            
        Returns:
            Concept URI if found, None otherwise
        """
        label_lower = label.lower().strip()
        
        sparql = f"""
        SELECT ?concept
        WHERE {{
            ?concept a syn:Concept .
            {{
                ?concept syn:label "{label_lower}" .
            }} UNION {{
                ?concept syn:altLabel "{label_lower}" .
            }}
        }}
        LIMIT 1
        """
        
        results = await self.query(user_id, sparql)
        if results:
            return results[0].get("concept")
        return None

    async def find_similar_concepts(
        self,
        user_id: str,
        label: str,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Find concepts with similar labels using FILTER.
        
        Args:
            user_id: User identifier
            label: Label to search for
            limit: Maximum results
            
        Returns:
            List of concepts with label and uri
        """
        label_lower = label.lower().strip()
        
        sparql = f"""
        SELECT DISTINCT ?concept ?conceptLabel ?altLabel
        WHERE {{
            ?concept a syn:Concept ;
                     syn:label ?conceptLabel .
            OPTIONAL {{ ?concept syn:altLabel ?altLabel }}
            FILTER(
                CONTAINS(LCASE(?conceptLabel), "{label_lower}") ||
                CONTAINS(LCASE(COALESCE(?altLabel, "")), "{label_lower}")
            )
        }}
        LIMIT {limit}
        """
        
        return await self.query(user_id, sparql)

    async def get_concept_with_definition(
        self,
        user_id: str,
        concept_uri: str,
    ) -> Optional[dict[str, Any]]:
        """
        Get a concept with its definition text.
        
        Args:
            user_id: User identifier
            concept_uri: Concept URI
            
        Returns:
            Dict with concept details or None
        """
        sparql = f"""
        SELECT ?label ?definitionText ?sourceTitle ?sourceUrl
        WHERE {{
            <{concept_uri}> syn:label ?label .
            OPTIONAL {{
                <{concept_uri}> syn:hasDefinition ?def .
                ?def syn:definitionText ?definitionText .
            }}
            OPTIONAL {{
                <{concept_uri}> syn:definedIn ?chunk .
                ?chunk syn:derivedFrom ?source .
                ?source syn:sourceTitle ?sourceTitle .
                ?source syn:sourceUrl ?sourceUrl .
            }}
        }}
        LIMIT 1
        """
        
        results = await self.query(user_id, sparql)
        return results[0] if results else None

    async def get_concept_relationships(
        self,
        user_id: str,
        concept_uri: str,
    ) -> list[dict[str, Any]]:
        """
        Get all relationships for a concept.
        
        Args:
            user_id: User identifier
            concept_uri: Concept URI
            
        Returns:
            List of relationships with type, target concept, and label
        """
        sparql = f"""
        SELECT ?relationType ?relatedConcept ?relatedLabel
        WHERE {{
            {{
                <{concept_uri}> ?relationType ?relatedConcept .
                ?relatedConcept a syn:Concept ;
                               syn:label ?relatedLabel .
                FILTER(?relationType IN (
                    syn:isA, syn:partOf, syn:prerequisiteFor, 
                    syn:relatedTo, syn:oppositeOf, syn:usedIn
                ))
            }} UNION {{
                ?relatedConcept ?relationType <{concept_uri}> .
                ?relatedConcept a syn:Concept ;
                               syn:label ?relatedLabel .
                FILTER(?relationType IN (
                    syn:isA, syn:partOf, syn:prerequisiteFor, 
                    syn:relatedTo, syn:oppositeOf, syn:usedIn
                ))
            }}
        }}
        """
        
        return await self.query(user_id, sparql)

    async def get_user_concepts(
        self,
        user_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """
        Get all concepts for a user.
        
        Args:
            user_id: User identifier
            limit: Maximum results
            offset: Pagination offset
            
        Returns:
            List of concepts with labels
        """
        sparql = f"""
        SELECT ?concept ?label ?hasDefinition
        WHERE {{
            ?concept a syn:Concept ;
                     syn:label ?label .
            BIND(EXISTS {{ ?concept syn:hasDefinition ?def }} AS ?hasDefinition)
        }}
        ORDER BY ?label
        LIMIT {limit}
        OFFSET {offset}
        """
        
        return await self.query(user_id, sparql)

    async def delete_concept(
        self,
        user_id: str,
        concept_uri: str,
    ) -> None:
        """
        Delete a concept and all its relationships.
        
        Args:
            user_id: User identifier
            concept_uri: Concept URI to delete
        """
        graph_uri = build_user_graph_uri(user_id)
        
        sparql = f"""
        {get_sparql_prefixes()}
        
        DELETE WHERE {{
            GRAPH <{graph_uri}> {{
                <{concept_uri}> ?p ?o .
            }}
        }};
        
        DELETE WHERE {{
            GRAPH <{graph_uri}> {{
                ?s ?p <{concept_uri}> .
            }}
        }}
        """
        
        await self._execute_update(sparql)
        logger.info("Concept deleted", user_id=user_id, concept_uri=concept_uri)

    async def _execute_query(
        self,
        sparql: str,
        result_format: str = "json",
    ) -> dict[str, Any]:
        """
        Execute a SPARQL query.
        
        Args:
            sparql: SPARQL query string
            result_format: Desired result format (json, xml, csv)
            
        Returns:
            Query results
        """
        accept_map = {
            "json": "application/sparql-results+json",
            "xml": "application/sparql-results+xml",
            "csv": "text/csv",
        }
        
        try:
            logger.info("Executing SPARQL query", query=sparql)
            
            response = await self.client.post(
                self.query_endpoint,
                data={"query": sparql},
                headers={
                    "Accept": accept_map.get(result_format, "application/sparql-results+json"),
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            )
            
            response.raise_for_status()
            
            if result_format == "json":
                data = response.json()
                logger.info("SPARQL results", results=data)
                return data
                
            return response.text
            
        except httpx.RequestError as e:
            logger.error("Fuseki request failed", error=str(e))
            raise StorageError(
                message=f"Fuseki request failed: {str(e)}",
                store_type="fuseki",
                operation="query",
                cause=e,
            )

    async def _execute_update(self, sparql: str) -> None:
        """
        Execute a SPARQL UPDATE.
        
        Args:
            sparql: SPARQL update string
        """
        try:
            response = await self.client.post(
                self.update_endpoint,
                data={"update": sparql},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            
            if response.status_code not in (200, 204):
                logger.error(
                    "SPARQL update failed",
                    status=response.status_code,
                    response=response.text[:500],
                    update=sparql[:200],
                )
                raise StorageError(
                    message=f"SPARQL update failed: {response.text[:200]}",
                    store_type="fuseki",
                    operation="update",
                )
                
        except httpx.RequestError as e:
            logger.error("Fuseki update request failed", error=str(e))
            raise StorageError(
                message=f"Fuseki update request failed: {str(e)}",
                store_type="fuseki",
                operation="update",
                cause=e,
            )

    async def update(
        self,
        user_id: str,
        sparql: str,
    ) -> None:
        """
        Execute a SPARQL UPDATE scoped to a user's graph.
        
        Automatically injects graph URI and prefixes.
        
        Args:
            user_id: User identifier
            sparql: SPARQL UPDATE query
        """
        graph_uri = build_user_graph_uri(user_id)
        
        # Build full query with prefixes and graph scoping
        # Replace WHERE clause to scope to user graph using WITH
        full_sparql = f"{get_sparql_prefixes()}\nWITH <{graph_uri}>\n{sparql}"
        
        await self._execute_update(full_sparql)

    def _now_iso(self) -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()

    async def get_graph_stats(self, user_id: str) -> dict[str, Any]:
        """
        Get statistics for a user's graph.
        
        Args:
            user_id: User identifier
            
        Returns:
            Dict with concept count, chunk count, etc.
        """
        # Use separate COUNT queries to avoid Cartesian product from OPTIONAL
        # Each count is independent and fast
        concept_sparql = """
        SELECT (COUNT(DISTINCT ?concept) AS ?count)
        WHERE { ?concept a syn:Concept }
        """
        
        chunk_sparql = """
        SELECT (COUNT(DISTINCT ?chunk) AS ?count)
        WHERE { ?chunk a syn:Chunk }
        """
        
        source_sparql = """
        SELECT (COUNT(DISTINCT ?source) AS ?count)
        WHERE { ?source a syn:Source }
        """
        
        definition_sparql = """
        SELECT (COUNT(DISTINCT ?def) AS ?count)
        WHERE { ?def a syn:Definition }
        """
        
        relationship_sparql = """
        SELECT (COUNT(*) AS ?count)
        WHERE {
            ?s ?relType ?o .
            ?s a syn:Concept .
            ?o a syn:Concept .
            FILTER(?relType IN (
                syn:isA, syn:partOf, syn:prerequisiteFor, 
                syn:relatedTo, syn:oppositeOf, syn:usedIn
            ))
        }
        """
        
        # Execute all queries in parallel using asyncio.gather
        import asyncio
        
        results = await asyncio.gather(
            self.query(user_id, concept_sparql),
            self.query(user_id, chunk_sparql),
            self.query(user_id, source_sparql),
            self.query(user_id, definition_sparql),
            self.query(user_id, relationship_sparql),
            return_exceptions=True
        )
        
        # Extract counts safely
        def safe_count(result, default=0):
            if isinstance(result, Exception):
                logger.warning("Stats query failed", error=str(result))
                return default
            if result and len(result) > 0:
                return int(result[0].get("count", default))
            return default
        
        return {
            "concept_count": safe_count(results[0]),
            "chunk_count": safe_count(results[1]),
            "source_count": safe_count(results[2]),
            "definition_count": safe_count(results[3]),
            "relationship_count": safe_count(results[4]),
        }

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()

