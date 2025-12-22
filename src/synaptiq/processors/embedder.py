"""
Embedding generator using OpenAI's embedding models.
"""

import asyncio
from typing import Optional

import structlog
from openai import AsyncOpenAI
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config.settings import get_settings
from synaptiq.core.exceptions import ProcessingError, RateLimitError
from synaptiq.core.schemas import Chunk, ProcessedChunk
from synaptiq.processors.base import ChunksToProcessedProcessor

logger = structlog.get_logger(__name__)


class EmbeddingGenerator(ChunksToProcessedProcessor):
    """
    Generates embeddings for chunks using OpenAI's embedding API.
    
    Features:
    - Batch processing for efficiency
    - Automatic retry with exponential backoff
    - Rate limit handling
    """

    def __init__(
        self,
        model: Optional[str] = None,
        dimensions: Optional[int] = None,
        batch_size: int = 100,
    ):
        """
        Initialize the embedding generator.
        
        Args:
            model: OpenAI embedding model (default from settings)
            dimensions: Embedding dimensions (default from settings)
            batch_size: Number of texts to embed per API call
        """
        settings = get_settings()
        self.model = model or settings.embedding_model
        self.dimensions = dimensions or settings.embedding_dimensions
        self.batch_size = batch_size

        self.client = AsyncOpenAI(api_key=settings.openai_api_key)

        logger.info(
            "EmbeddingGenerator initialized",
            model=self.model,
            dimensions=self.dimensions,
            batch_size=batch_size,
        )

    async def process(self, chunks: list[Chunk]) -> list[ProcessedChunk]:
        """
        Generate embeddings for all chunks.
        
        Args:
            chunks: Chunks to embed
            
        Returns:
            ProcessedChunks with embeddings
        """
        if not chunks:
            return []

        logger.info("Generating embeddings", chunk_count=len(chunks))

        # Process in batches
        processed_chunks = []
        texts = [chunk.text for chunk in chunks]

        for i in range(0, len(texts), self.batch_size):
            batch_texts = texts[i : i + self.batch_size]
            batch_chunks = chunks[i : i + self.batch_size]

            logger.debug(
                "Processing embedding batch",
                batch_start=i,
                batch_size=len(batch_texts),
            )

            try:
                embeddings = await self._generate_embeddings_batch(batch_texts)

                for chunk, embedding in zip(batch_chunks, embeddings):
                    processed_chunks.append(
                        ProcessedChunk(
                            id=chunk.id,
                            document_id=chunk.document_id,
                            user_id=chunk.user_id,
                            chunk_index=chunk.chunk_index,
                            vector=embedding,
                            text=chunk.text,
                            source_type=chunk.source_type.value,
                            source_url=chunk.source_url,
                            source_title=chunk.source_title,
                            timestamp_start_ms=chunk.timestamp_start_ms,
                            timestamp_end_ms=chunk.timestamp_end_ms,
                            concepts=chunk.concepts,
                            has_definition=chunk.has_definition,
                        )
                    )

            except Exception as e:
                logger.error(
                    "Embedding batch failed",
                    batch_start=i,
                    error=str(e),
                )
                raise ProcessingError(
                    message=f"Failed to generate embeddings: {str(e)}",
                    processor_name=self.name,
                    cause=e,
                )

        logger.info(
            "Embeddings generated successfully",
            chunk_count=len(processed_chunks),
        )

        return processed_chunks

    @retry(
        retry=retry_if_exception_type((RateLimitError,)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=60),
    )
    async def _generate_embeddings_batch(
        self, texts: list[str]
    ) -> list[list[float]]:
        """
        Generate embeddings for a batch of texts.
        
        Args:
            texts: Texts to embed
            
        Returns:
            List of embedding vectors
        """
        try:
            response = await self.client.embeddings.create(
                model=self.model,
                input=texts,
                dimensions=self.dimensions,
            )

            # Sort by index to maintain order
            embeddings_by_index = {
                item.index: item.embedding for item in response.data
            }
            return [embeddings_by_index[i] for i in range(len(texts))]

        except Exception as e:
            error_message = str(e).lower()

            if "rate limit" in error_message:
                logger.warning("Rate limit hit, will retry", error=str(e))
                raise RateLimitError(
                    message="OpenAI rate limit exceeded",
                    retry_after=60,
                    cause=e,
                )

            raise

    async def generate_single(self, text: str) -> list[float]:
        """
        Generate embedding for a single text.
        
        Useful for query embedding.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector
        """
        embeddings = await self._generate_embeddings_batch([text])
        return embeddings[0]


