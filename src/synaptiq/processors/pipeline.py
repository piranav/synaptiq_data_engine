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

logger = structlog.get_logger(__name__)


class Pipeline:
    """
    Orchestrates the processing pipeline.
    
    The pipeline transforms a CanonicalDocument through:
    1. Chunking: Document -> Chunk[]
    2. Processing: Chunk[] -> Chunk[] (concept extraction, etc.)
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
            processors: List of intermediate processors (default: [ConceptExtractor])
            embedder: Custom embedder (default: EmbeddingGenerator)
        """
        self.chunker = chunker or SemanticChunker()
        self.processors = processors if processors is not None else [ConceptExtractor()]
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
    Create a pipeline with default configuration.
    
    Returns:
        Pipeline with SemanticChunker, ConceptExtractor, and EmbeddingGenerator
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
    
    Returns:
        Pipeline with SemanticChunker and EmbeddingGenerator only
    """
    return Pipeline(
        chunker=SemanticChunker(),
        processors=[],
        embedder=EmbeddingGenerator(),
    )


