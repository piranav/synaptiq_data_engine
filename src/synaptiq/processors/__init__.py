"""Processing pipeline components."""

from synaptiq.processors.base import Processor
from synaptiq.processors.chunker import SemanticChunker
from synaptiq.processors.concept_extractor import (
    ConceptExtractor,
    ConceptExtractorDisabled,
    ExtractedRelationship,
)
from synaptiq.processors.embedder import EmbeddingGenerator

# Lazy imports to avoid circular dependencies with ontology package


def __getattr__(name: str):
    """Lazy import for modules that have circular dependencies."""
    if name in ("Pipeline", "create_default_pipeline", "create_pipeline_with_ontology",
                "create_pipeline_without_ontology", "create_pipeline_without_concepts"):
        from synaptiq.processors.pipeline import (
            Pipeline,
            create_default_pipeline,
            create_pipeline_with_ontology,
            create_pipeline_without_ontology,
            create_pipeline_without_concepts,
        )
        return locals()[name]
    
    if name in ("OntologyWriter", "OntologyWriterDisabled"):
        from synaptiq.processors.ontology_writer import OntologyWriter, OntologyWriterDisabled
        return locals()[name]
    
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "Processor",
    "Pipeline",
    "create_default_pipeline",
    "create_pipeline_with_ontology",
    "create_pipeline_without_ontology",
    "create_pipeline_without_concepts",
    "SemanticChunker",
    "ConceptExtractor",
    "ConceptExtractorDisabled",
    "ExtractedRelationship",
    "EmbeddingGenerator",
    "OntologyWriter",
    "OntologyWriterDisabled",
]

