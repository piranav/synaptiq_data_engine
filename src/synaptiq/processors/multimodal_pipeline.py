"""
Multimodal pipeline for knowledge extraction from notes.

Orchestrates the processing of notes with mixed content types:
- Text blocks → Semantic chunking → Embeddings
- Tables → Structured parsing + Description → Embeddings
- Images → Vision analysis → Embeddings
- Code → Explanation → Embeddings
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from synaptiq.processors.chunker import SemanticChunker
from synaptiq.processors.code_processor import CodeExtractionResult, CodeProcessor
from synaptiq.processors.concept_extractor import ConceptExtractor
from synaptiq.processors.content_splitter import ContentBlock, ContentSplitter, ContentType
from synaptiq.processors.context_linker import ContextEnrichedArtifact, ContextLinker
from synaptiq.processors.embedder import EmbeddingGenerator
from synaptiq.processors.image_processor import ImageExtractionResult, ImageProcessor
from synaptiq.processors.table_processor import TableExtractionResult, TableProcessor
from synaptiq.core.schemas import Chunk, ProcessedChunk

logger = structlog.get_logger(__name__)


@dataclass
class ProcessedArtifact:
    """A fully processed artifact ready for storage."""
    id: str
    type: str  # table, image, code, mermaid
    note_id: str
    user_id: str
    
    # Position and context
    position_in_source: int
    context_before: str
    context_after: str
    raw_content: str
    
    # LLM-generated
    description: str
    combined_text_for_embedding: str
    
    # Embedding
    embedding: Optional[list[float]] = None
    
    # Type-specific data
    extraction_data: dict = field(default_factory=dict)
    
    # For tables: row-level facts
    row_facts: list[str] = field(default_factory=list)
    row_fact_embeddings: list[list[float]] = field(default_factory=list)
    
    # Extracted concepts
    concepts: list[str] = field(default_factory=list)


@dataclass
class MultimodalExtractionResult:
    """Result of multimodal extraction from a note."""
    note_id: str
    user_id: str
    
    # Text processing results
    text_chunks: list[ProcessedChunk]
    
    # Artifact processing results
    artifacts: list[ProcessedArtifact]
    
    # Unified concepts across all content
    all_concepts: list[str]
    
    # Statistics
    processing_time_ms: int = 0
    text_block_count: int = 0
    table_count: int = 0
    image_count: int = 0
    code_count: int = 0
    mermaid_count: int = 0


class MultimodalPipeline:
    """
    Orchestrates multimodal knowledge extraction from notes.
    
    Flow:
    1. Split content by type (text, tables, images, code)
    2. Process each type with specialized processors
    3. Enrich artifacts with context
    4. Extract unified concepts
    5. Generate embeddings
    6. Return structured results for storage
    """
    
    def __init__(
        self,
        content_splitter: Optional[ContentSplitter] = None,
        text_chunker: Optional[SemanticChunker] = None,
        table_processor: Optional[TableProcessor] = None,
        image_processor: Optional[ImageProcessor] = None,
        code_processor: Optional[CodeProcessor] = None,
        context_linker: Optional[ContextLinker] = None,
        concept_extractor: Optional[ConceptExtractor] = None,
        embedder: Optional[EmbeddingGenerator] = None,
    ):
        """
        Initialize the multimodal pipeline.
        
        All components are optional and use defaults if not provided.
        """
        self.splitter = content_splitter or ContentSplitter()
        self.text_chunker = text_chunker or SemanticChunker()
        self.table_processor = table_processor or TableProcessor()
        self.image_processor = image_processor or ImageProcessor()
        self.code_processor = code_processor or CodeProcessor()
        self.context_linker = context_linker or ContextLinker()
        self.concept_extractor = concept_extractor or ConceptExtractor()
        self.embedder = embedder or EmbeddingGenerator()
        
        logger.info("MultimodalPipeline initialized")
    
    async def process_note(
        self,
        note_content: list[dict] | str,
        note_id: str,
        user_id: str,
        note_title: str = "Untitled",
        fetch_images: bool = True,
    ) -> MultimodalExtractionResult:
        """
        Process a note for knowledge extraction.
        
        Args:
            note_content: TipTap JSON content or raw markdown
            note_id: Note ID for linking
            user_id: User ID for isolation
            note_title: Note title for context
            fetch_images: Whether to fetch external images
            
        Returns:
            MultimodalExtractionResult with all processed content
        """
        start_time = datetime.now(timezone.utc)
        
        logger.info(
            "Starting multimodal extraction",
            note_id=note_id,
            user_id=user_id,
        )
        
        # 1. Split content by type
        blocks = self.splitter.split(note_content)
        
        # Categorize blocks
        text_blocks = [b for b in blocks if b.type == ContentType.TEXT]
        table_blocks = [b for b in blocks if b.type == ContentType.TABLE]
        image_blocks = [b for b in blocks if b.type == ContentType.IMAGE]
        code_blocks = [b for b in blocks if b.type == ContentType.CODE]
        mermaid_blocks = [b for b in blocks if b.type == ContentType.MERMAID]
        
        logger.info(
            "Content split",
            text=len(text_blocks),
            tables=len(table_blocks),
            images=len(image_blocks),
            code=len(code_blocks),
            mermaid=len(mermaid_blocks),
        )
        
        # 2. Process each type in parallel
        text_task = self._process_text_blocks(text_blocks, note_id, user_id, note_title)
        table_task = self._process_table_blocks(table_blocks, note_id, user_id, note_title)
        image_task = self._process_image_blocks(image_blocks, note_id, user_id, note_title, fetch_images)
        code_task = self._process_code_blocks(code_blocks + mermaid_blocks, note_id, user_id, note_title)
        
        text_chunks, table_artifacts, image_artifacts, code_artifacts = await asyncio.gather(
            text_task, table_task, image_task, code_task
        )
        
        # 3. Combine all artifacts
        all_artifacts = table_artifacts + image_artifacts + code_artifacts
        
        # 4. Extract unified concepts
        all_concepts = await self._extract_unified_concepts(text_chunks, all_artifacts)
        
        # 5. Generate embeddings for artifacts
        all_artifacts = await self._generate_artifact_embeddings(all_artifacts)
        
        # Calculate processing time
        end_time = datetime.now(timezone.utc)
        processing_time_ms = int((end_time - start_time).total_seconds() * 1000)
        
        logger.info(
            "Multimodal extraction complete",
            note_id=note_id,
            text_chunks=len(text_chunks),
            artifacts=len(all_artifacts),
            concepts=len(all_concepts),
            time_ms=processing_time_ms,
        )
        
        return MultimodalExtractionResult(
            note_id=note_id,
            user_id=user_id,
            text_chunks=text_chunks,
            artifacts=all_artifacts,
            all_concepts=all_concepts,
            processing_time_ms=processing_time_ms,
            text_block_count=len(text_blocks),
            table_count=len(table_blocks),
            image_count=len(image_blocks),
            code_count=len(code_blocks),
            mermaid_count=len(mermaid_blocks),
        )
    
    async def _process_text_blocks(
        self,
        blocks: list[ContentBlock],
        note_id: str,
        user_id: str,
        note_title: str,
    ) -> list[ProcessedChunk]:
        """Process text blocks through semantic chunking."""
        if not blocks:
            return []
        
        # Combine text blocks
        combined_text = "\n\n".join(b.content for b in blocks)
        
        # Create a minimal document for chunking
        from synaptiq.core.schemas import CanonicalDocument, SourceType
        
        doc = CanonicalDocument(
            id=note_id,
            user_id=user_id,
            source_type=SourceType.NOTE,
            source_url=f"note://{note_id}",
            source_title=note_title,
            raw_content=combined_text,
        )
        
        # Chunk the text
        chunks = await self.text_chunker.process(doc)
        
        # Extract concepts
        chunks = await self.concept_extractor.process(chunks)
        
        # Generate embeddings
        processed_chunks = await self.embedder.process(chunks)
        
        return processed_chunks
    
    async def _process_table_blocks(
        self,
        blocks: list[ContentBlock],
        note_id: str,
        user_id: str,
        note_title: str,
    ) -> list[ProcessedArtifact]:
        """Process table blocks."""
        artifacts = []
        
        for block in blocks:
            try:
                # Process table
                result: TableExtractionResult = await self.table_processor.process(block)
                
                # Create artifact
                artifact = ProcessedArtifact(
                    id=str(uuid4()),
                    type="table",
                    note_id=note_id,
                    user_id=user_id,
                    position_in_source=block.start_offset,
                    context_before=block.context_before,
                    context_after=block.context_after,
                    raw_content=block.content,
                    description=result.description,
                    combined_text_for_embedding=result.combined_text,
                    extraction_data={
                        "structured": {
                            "headers": result.structured.headers,
                            "rows": result.structured.rows,
                            "row_count": result.structured.row_count,
                            "column_count": result.structured.column_count,
                        }
                    },
                    row_facts=result.row_facts,
                    concepts=result.concepts,
                )
                artifacts.append(artifact)
                
            except Exception as e:
                logger.warning("Failed to process table", error=str(e))
        
        return artifacts
    
    async def _process_image_blocks(
        self,
        blocks: list[ContentBlock],
        note_id: str,
        user_id: str,
        note_title: str,
        fetch_images: bool,
    ) -> list[ProcessedArtifact]:
        """Process image blocks."""
        artifacts = []
        
        for block in blocks:
            try:
                # Fetch image if needed
                image_bytes = None
                if fetch_images and not block.metadata.get("is_base64"):
                    image_bytes = await self._fetch_image(block.metadata.get("url"))
                
                # Process image
                result: ImageExtractionResult = await self.image_processor.process(
                    block, image_bytes
                )
                
                # Create artifact
                artifact = ProcessedArtifact(
                    id=str(uuid4()),
                    type="image",
                    note_id=note_id,
                    user_id=user_id,
                    position_in_source=block.start_offset,
                    context_before=block.context_before,
                    context_after=block.context_after,
                    raw_content=block.content,
                    description=result.description,
                    combined_text_for_embedding=result.combined_text,
                    extraction_data={
                        "image_type": result.image_type.value,
                        "components": result.components,
                        "relationships": result.relationships,
                        "ocr_text": result.ocr_text,
                        "data_points": result.data_points,
                        "original_url": result.original_url,
                    },
                    concepts=result.concepts,
                )
                artifacts.append(artifact)
                
            except Exception as e:
                logger.warning("Failed to process image", error=str(e))
        
        return artifacts
    
    async def _process_code_blocks(
        self,
        blocks: list[ContentBlock],
        note_id: str,
        user_id: str,
        note_title: str,
    ) -> list[ProcessedArtifact]:
        """Process code and mermaid blocks."""
        artifacts = []
        
        for block in blocks:
            try:
                # Process code
                result: CodeExtractionResult = await self.code_processor.process(block)
                
                artifact_type = "mermaid" if result.is_mermaid else "code"
                
                # Create artifact
                artifact = ProcessedArtifact(
                    id=str(uuid4()),
                    type=artifact_type,
                    note_id=note_id,
                    user_id=user_id,
                    position_in_source=block.start_offset,
                    context_before=block.context_before,
                    context_after=block.context_after,
                    raw_content=block.content,
                    description=result.explanation,
                    combined_text_for_embedding=result.combined_text,
                    extraction_data={
                        "language": result.language,
                        "is_mermaid": result.is_mermaid,
                        "mermaid_type": result.mermaid_type,
                        "mermaid_components": result.mermaid_components,
                        "mermaid_relationships": result.mermaid_relationships,
                    },
                    concepts=result.extracted_concepts,
                )
                artifacts.append(artifact)
                
            except Exception as e:
                logger.warning("Failed to process code block", error=str(e))
        
        return artifacts
    
    async def _extract_unified_concepts(
        self,
        text_chunks: list[ProcessedChunk],
        artifacts: list[ProcessedArtifact],
    ) -> list[str]:
        """Extract and unify concepts from all content."""
        all_concepts = set()
        
        # Concepts from text chunks
        for chunk in text_chunks:
            all_concepts.update(chunk.concepts)
        
        # Concepts from artifacts
        for artifact in artifacts:
            all_concepts.update(artifact.concepts)
        
        return list(all_concepts)
    
    async def _generate_artifact_embeddings(
        self,
        artifacts: list[ProcessedArtifact],
    ) -> list[ProcessedArtifact]:
        """Generate embeddings for artifacts."""
        if not artifacts:
            return artifacts
        
        # Collect all texts to embed
        texts_to_embed = []
        for artifact in artifacts:
            texts_to_embed.append(artifact.combined_text_for_embedding)
            texts_to_embed.extend(artifact.row_facts)
        
        if not texts_to_embed:
            return artifacts
        
        # Generate embeddings in batch
        embeddings = await self.embedder._generate_embeddings_batch(texts_to_embed)
        
        # Assign embeddings back to artifacts
        embed_idx = 0
        for artifact in artifacts:
            # Main embedding
            artifact.embedding = embeddings[embed_idx]
            embed_idx += 1
            
            # Row fact embeddings (for tables)
            for _ in artifact.row_facts:
                artifact.row_fact_embeddings.append(embeddings[embed_idx])
                embed_idx += 1
        
        return artifacts
    
    async def _fetch_image(self, url: Optional[str]) -> Optional[bytes]:
        """Fetch image from URL."""
        if not url:
            return None
        
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        return await response.read()
        except Exception as e:
            logger.warning("Failed to fetch image", url=url[:100], error=str(e))
        
        return None
