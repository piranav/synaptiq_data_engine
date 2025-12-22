"""
Base processor protocol and types for the processing pipeline.
"""

from abc import ABC, abstractmethod
from typing import Protocol, runtime_checkable

from synaptiq.core.schemas import Chunk, CanonicalDocument, ProcessedChunk


@runtime_checkable
class Processor(Protocol):
    """
    Protocol for pipeline processors.
    
    Each processor takes a list of chunks and returns a modified list.
    Processors can:
    - Transform chunks (e.g., add embeddings)
    - Filter chunks
    - Enrich chunks with metadata (e.g., concepts)
    - Split or merge chunks
    """

    @property
    def name(self) -> str:
        """Processor name for logging and debugging."""
        ...

    async def process(self, chunks: list[Chunk]) -> list[Chunk]:
        """
        Process a list of chunks.
        
        Args:
            chunks: Input chunks to process
            
        Returns:
            Processed chunks (may be same, fewer, or more than input)
        """
        ...


class BaseProcessor(ABC):
    """
    Abstract base class for processors with common functionality.
    """

    @property
    def name(self) -> str:
        """Return the class name as the processor name."""
        return self.__class__.__name__

    @abstractmethod
    async def process(self, chunks: list[Chunk]) -> list[Chunk]:
        """Process chunks - must be implemented by subclasses."""
        pass

    def __repr__(self) -> str:
        return f"<{self.name}>"


class DocumentToChunksProcessor(ABC):
    """
    Abstract base class for processors that convert documents to chunks.
    
    This is typically the first processor in the pipeline (the chunker).
    """

    @property
    def name(self) -> str:
        """Return the class name as the processor name."""
        return self.__class__.__name__

    @abstractmethod
    async def process(self, document: CanonicalDocument) -> list[Chunk]:
        """
        Convert a document to a list of chunks.
        
        Args:
            document: The canonical document to chunk
            
        Returns:
            List of chunks created from the document
        """
        pass


class ChunksToProcessedProcessor(ABC):
    """
    Abstract base class for processors that convert chunks to processed chunks.
    
    This is typically the final processor that adds embeddings.
    """

    @property
    def name(self) -> str:
        """Return the class name as the processor name."""
        return self.__class__.__name__

    @abstractmethod
    async def process(self, chunks: list[Chunk]) -> list[ProcessedChunk]:
        """
        Convert chunks to processed chunks with embeddings.
        
        Args:
            chunks: Chunks to process
            
        Returns:
            Processed chunks with embeddings
        """
        pass


