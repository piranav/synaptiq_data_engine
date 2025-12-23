"""
Agent context for dependency injection.

The context is passed to all agents, tools, and handoffs during execution.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from synaptiq.storage.fuseki import FusekiStore
    from synaptiq.storage.qdrant import QdrantStore
    from synaptiq.processors.embeddings import EmbeddingGenerator


@dataclass
class AgentContext:
    """
    Context passed to all agents and tools during execution.
    
    This serves as a dependency injection mechanism, providing:
    - User identification for multi-tenant scoping
    - Store references for data access
    - Ontology schema for SPARQL generation
    
    Attributes:
        user_id: User identifier for graph scoping
        fuseki_store: SPARQL client for knowledge graph
        qdrant_store: Vector store client for embeddings
        embedding_generator: OpenAI embeddings generator
        ontology_schema: TTL content for SPARQL agent prompt
    """
    
    user_id: str
    fuseki_store: "FusekiStore"
    qdrant_store: "QdrantStore"
    embedding_generator: "EmbeddingGenerator"
    ontology_schema: str
    
    def get_user_graph_uri(self) -> str:
        """Get the named graph URI for this user."""
        from synaptiq.ontology.namespaces import build_user_graph_uri
        return build_user_graph_uri(self.user_id)
    
    def get_sparql_prefixes(self) -> str:
        """Get SPARQL PREFIX declarations."""
        from synaptiq.ontology.namespaces import get_sparql_prefixes
        return get_sparql_prefixes()
