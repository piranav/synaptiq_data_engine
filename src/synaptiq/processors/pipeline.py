"""
Processing pipeline orchestrator.
"""

from typing import Optional

import structlog

from synaptiq.core.exceptions import ProcessingError
from synaptiq.core.schemas import CanonicalDocument, Chunk, ProcessedChunk
from synaptiq.processors.base import BaseProcessor, Processor
from synaptiq.processors.chunker import SemanticChunker
from synaptiq.processors.concept_extractor import ConceptExtractor
from synaptiq.processors.embedder import EmbeddingGenerator
from synaptiq.processors.ontology_writer import OntologyWriter

logger = structlog.get_logger(__name__)


class Pipeline:
    """
    Orchestrates the processing pipeline.
    
    The pipeline transforms a CanonicalDocument through:
    1. Chunking: Document -> Chunk[]
    2. Processing: Chunk[] -> Chunk[] (concept extraction, ontology writing, etc.)
    3. Embedding: Chunk[] -> ProcessedChunk[]
    """

    def __init__(
        self,
        chunker: Optional[SemanticChunker] = None,
        processors: Optional[list[BaseProcessor]] = None,
        embedder: Optional[EmbeddingGenerator] = None,
    ):
        """
        Initialize the pipeline with optional custom components.
        
        Args:
            chunker: Custom chunker (default: SemanticChunker)
            processors: List of intermediate processors (default: [ConceptExtractor, OntologyWriter])
            embedder: Custom embedder (default: EmbeddingGenerator)
        """
        self.chunker = chunker or SemanticChunker()
        self.processors = processors if processors is not None else [
            ConceptExtractor(),
            OntologyWriter(),
        ]
        self.embedder = embedder or EmbeddingGenerator()

        logger.info(
            "Pipeline initialized",
            chunker=self.chunker.name,
            processors=[p.name for p in self.processors],
            embedder=self.embedder.name,
        )

    async def run(self, document: CanonicalDocument) -> list[ProcessedChunk]:
        """
        Run the complete processing pipeline on a document.
        
        Args:
            document: The canonical document to process
            
        Returns:
            List of processed chunks with embeddings
        """
        logger.info(
            "Starting pipeline",
            document_id=document.id,
            source_type=document.source_type,
        )

        try:
            # Step 1: Chunking
            logger.debug("Running chunker", chunker=self.chunker.name)
            chunks = await self.chunker.process(document)
            logger.info("Chunking complete", chunk_count=len(chunks))

            # Step 2: Run intermediate processors
            for processor in self.processors:
                logger.debug("Running processor", processor=processor.name)
                chunks = await processor.process(chunks)
                logger.debug(
                    "Processor complete",
                    processor=processor.name,
                    chunk_count=len(chunks),
                )

            # Step 3: Generate embeddings
            logger.debug("Running embedder", embedder=self.embedder.name)
            processed_chunks = await self.embedder.process(chunks)

            logger.info(
                "Pipeline complete",
                document_id=document.id,
                processed_chunk_count=len(processed_chunks),
            )

            return processed_chunks

        except ProcessingError:
            raise
        except Exception as e:
            logger.error(
                "Pipeline failed",
                document_id=document.id,
                error=str(e),
            )
            raise ProcessingError(
                message=f"Pipeline failed: {str(e)}",
                document_id=document.id,
                cause=e,
            )

    async def run_chunks_only(self, document: CanonicalDocument) -> list[Chunk]:
        """
        Run only the chunking and processing steps (no embeddings).
        
        Useful for testing or when you want to inspect chunks.
        
        Args:
            document: The canonical document to process
            
        Returns:
            List of processed chunks (without embeddings)
        """
        chunks = await self.chunker.process(document)

        for processor in self.processors:
            chunks = await processor.process(chunks)

        return chunks


def create_default_pipeline() -> Pipeline:
    """
    Create a pipeline with full ontology support.
    
    Includes:
    - SemanticChunker: Splits content into semantic chunks
    - ConceptExtractor: Extracts concepts, definitions, and relationships
    - OntologyWriter: Writes to RDF graph store (Fuseki)
    - EmbeddingGenerator: Creates vector embeddings
    
    Returns:
        Pipeline with full processing including graph storage
    """
    return Pipeline(
        chunker=SemanticChunker(),
        processors=[
            ConceptExtractor(),
            OntologyWriter(),
        ],
        embedder=EmbeddingGenerator(),
    )


def create_pipeline_with_ontology() -> Pipeline:
    """
    Create a pipeline with ontology support (explicit name).
    
    Same as create_default_pipeline() but with explicit naming.
    
    Returns:
        Pipeline with ConceptExtractor and OntologyWriter
    """
    return create_default_pipeline()


def create_pipeline_without_ontology() -> Pipeline:
    """
    Create a pipeline without ontology/graph storage.
    
    Useful when you want concept extraction but don't have
    Fuseki running or don't need graph storage.
    
    Returns:
        Pipeline with ConceptExtractor only (no OntologyWriter)
    """
    return Pipeline(
        chunker=SemanticChunker(),
        processors=[ConceptExtractor()],
        embedder=EmbeddingGenerator(),
    )


def create_pipeline_without_concepts() -> Pipeline:
    """
    Create a pipeline without concept extraction.
    
    Useful if you don't need LLM-based extraction.
    Just chunks and embeds content.
    
    Returns:
        Pipeline with SemanticChunker and EmbeddingGenerator only
    """
    return Pipeline(
        chunker=SemanticChunker(),
        processors=[],
        embedder=EmbeddingGenerator(),
    )


def create_minimal_pipeline() -> Pipeline:
    """
    Create a minimal pipeline for testing.
    
    Same as create_pipeline_without_concepts().
    
    Returns:
        Pipeline with chunking and embedding only
    """
    return create_pipeline_without_concepts()
