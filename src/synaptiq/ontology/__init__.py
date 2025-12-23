"""
Ontology package for RDF/SPARQL-based knowledge graph operations.

This package provides:
- Ontology definitions (synaptiq.ttl)
- URI namespace utilities
- Conflict resolution for concept disambiguation
- Graph management for user knowledge graphs

Note: To avoid circular imports, some classes are imported lazily.
Use direct imports for conflict_resolver and graph_manager:
    from synaptiq.ontology.conflict_resolver import ConflictResolver
    from synaptiq.ontology.graph_manager import GraphManager
"""

from synaptiq.ontology.namespaces import (
    SYNAPTIQ,
    RDF,
    RDFS,
    OWL,
    XSD,
    build_chunk_uri,
    build_concept_uri,
    build_definition_uri,
    build_source_uri,
    build_user_graph_uri,
    build_ontology_graph_uri,
    get_sparql_prefixes,
    get_relationship_uri,
    get_source_class_uri,
    slugify,
)

# Lazy imports to avoid circular dependencies
# These are re-exported for convenience but should be imported directly
# from their modules when used in other synaptiq packages


def __getattr__(name: str):
    """Lazy import for modules that have circular dependencies."""
    if name in ("ConflictResolver", "ConflictAction", "ConflictResolution", 
                "ExtractedConcept", "ExistingConcept"):
        from synaptiq.ontology.conflict_resolver import (
            ConflictResolver,
            ConflictAction,
            ConflictResolution,
            ExtractedConcept,
            ExistingConcept,
        )
        return locals()[name]
    
    if name == "GraphManager":
        from synaptiq.ontology.graph_manager import GraphManager
        return GraphManager
    
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # Namespaces
    "SYNAPTIQ",
    "RDF",
    "RDFS",
    "OWL",
    "XSD",
    # URI builders
    "build_user_graph_uri",
    "build_ontology_graph_uri",
    "build_concept_uri",
    "build_chunk_uri",
    "build_source_uri",
    "build_definition_uri",
    # Utilities
    "get_sparql_prefixes",
    "get_relationship_uri",
    "get_source_class_uri",
    "slugify",
    # Conflict resolution (lazy loaded)
    "ConflictResolver",
    "ConflictAction",
    "ConflictResolution",
    "ExtractedConcept",
    "ExistingConcept",
    # Graph management (lazy loaded)
    "GraphManager",
]

