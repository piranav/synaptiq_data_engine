"""
Semantic chunker for splitting documents into meaningful chunks.
"""

from typing import Optional

import structlog
import tiktoken

from config.settings import get_settings
from synaptiq.core.schemas import CanonicalDocument, Chunk, Segment, SourceType
from synaptiq.processors.base import DocumentToChunksProcessor

logger = structlog.get_logger(__name__)


class SemanticChunker(DocumentToChunksProcessor):
    """
    Chunks documents semantically, respecting natural boundaries.
    
    Features:
    - Respects segment boundaries from source (transcript timestamps, paragraphs)
    - Merges small segments to meet minimum chunk size
    - Splits large segments at sentence boundaries
    - Preserves timestamp information for citations
    """

    def __init__(
        self,
        max_tokens: Optional[int] = None,
        overlap_tokens: Optional[int] = None,
        min_chunk_tokens: int = 100,
    ):
        """
        Initialize the chunker.
        
        Args:
            max_tokens: Maximum tokens per chunk (default from settings)
            overlap_tokens: Token overlap between chunks (default from settings)
            min_chunk_tokens: Minimum tokens for a chunk (smaller gets merged)
        """
        settings = get_settings()
        self.max_tokens = max_tokens or settings.chunk_max_tokens
        self.overlap_tokens = overlap_tokens or settings.chunk_overlap_tokens
        self.min_chunk_tokens = min_chunk_tokens

        # Use cl100k_base encoding (used by text-embedding-3-small)
        self.encoder = tiktoken.get_encoding("cl100k_base")

    async def process(self, document: CanonicalDocument) -> list[Chunk]:
        """
        Chunk a document into semantically meaningful pieces.
        
        Args:
            document: The canonical document to chunk
            
        Returns:
            List of chunks preserving semantic boundaries
        """
        logger.info(
            "Chunking document",
            document_id=document.id,
            source_type=document.source_type,
            segment_count=len(document.content_segments),
        )

        # If document has natural segments, use them as basis
        if document.content_segments:
            chunks = self._chunk_from_segments(document)
        else:
            # Fall back to raw content chunking
            chunks = self._chunk_from_raw_content(document)

        logger.info(
            "Chunking complete",
            document_id=document.id,
            chunk_count=len(chunks),
        )

        return chunks

    def _chunk_from_segments(self, document: CanonicalDocument) -> list[Chunk]:
        """Create chunks from pre-segmented content."""
        chunks = []
        current_texts: list[str] = []
        current_tokens = 0
        current_start_offset: Optional[int] = None
        current_end_offset: Optional[int] = None
        chunk_index = 0

        for segment in document.content_segments:
            segment_tokens = self._count_tokens(segment.text)

            # If this single segment is too large, split it
            if segment_tokens > self.max_tokens:
                # First, flush current buffer
                if current_texts:
                    chunks.append(
                        self._create_chunk(
                            document=document,
                            text=" ".join(current_texts),
                            chunk_index=chunk_index,
                            start_offset=current_start_offset,
                            end_offset=current_end_offset,
                        )
                    )
                    chunk_index += 1
                    current_texts = []
                    current_tokens = 0
                    current_start_offset = None
                    current_end_offset = None

                # Split the large segment
                sub_chunks = self._split_large_segment(segment, document, chunk_index)
                chunks.extend(sub_chunks)
                chunk_index += len(sub_chunks)
                continue

            # Check if adding this segment would exceed max
            if current_tokens + segment_tokens > self.max_tokens and current_texts:
                # Create chunk from buffer
                chunks.append(
                    self._create_chunk(
                        document=document,
                        text=" ".join(current_texts),
                        chunk_index=chunk_index,
                        start_offset=current_start_offset,
                        end_offset=current_end_offset,
                    )
                )
                chunk_index += 1

                # Start new buffer with overlap
                overlap_text = self._get_overlap_text(current_texts)
                if overlap_text:
                    current_texts = [overlap_text]
                    current_tokens = self._count_tokens(overlap_text)
                else:
                    current_texts = []
                    current_tokens = 0
                current_start_offset = segment.start_offset
                current_end_offset = segment.end_offset

            # Add segment to buffer
            current_texts.append(segment.text)
            current_tokens += segment_tokens

            if current_start_offset is None:
                current_start_offset = segment.start_offset
            current_end_offset = segment.end_offset

        # Don't forget the last chunk
        if current_texts:
            chunks.append(
                self._create_chunk(
                    document=document,
                    text=" ".join(current_texts),
                    chunk_index=chunk_index,
                    start_offset=current_start_offset,
                    end_offset=current_end_offset,
                )
            )

        return chunks

    def _chunk_from_raw_content(self, document: CanonicalDocument) -> list[Chunk]:
        """Create chunks from raw content without segments."""
        chunks = []
        text = document.raw_content

        # Split by sentences for clean boundaries
        sentences = self._split_into_sentences(text)

        current_texts: list[str] = []
        current_tokens = 0
        chunk_index = 0

        for sentence in sentences:
            sentence_tokens = self._count_tokens(sentence)

            # Handle very long sentences
            if sentence_tokens > self.max_tokens:
                if current_texts:
                    chunks.append(
                        self._create_chunk(
                            document=document,
                            text=" ".join(current_texts),
                            chunk_index=chunk_index,
                        )
                    )
                    chunk_index += 1
                    current_texts = []
                    current_tokens = 0

                # Split long sentence by words
                words = sentence.split()
                word_buffer = []
                buffer_tokens = 0

                for word in words:
                    word_tokens = self._count_tokens(word + " ")
                    if buffer_tokens + word_tokens > self.max_tokens and word_buffer:
                        chunks.append(
                            self._create_chunk(
                                document=document,
                                text=" ".join(word_buffer),
                                chunk_index=chunk_index,
                            )
                        )
                        chunk_index += 1
                        word_buffer = []
                        buffer_tokens = 0
                    word_buffer.append(word)
                    buffer_tokens += word_tokens

                if word_buffer:
                    current_texts = [" ".join(word_buffer)]
                    current_tokens = buffer_tokens
                continue

            if current_tokens + sentence_tokens > self.max_tokens and current_texts:
                chunks.append(
                    self._create_chunk(
                        document=document,
                        text=" ".join(current_texts),
                        chunk_index=chunk_index,
                    )
                )
                chunk_index += 1

                overlap_text = self._get_overlap_text(current_texts)
                if overlap_text:
                    current_texts = [overlap_text]
                    current_tokens = self._count_tokens(overlap_text)
                else:
                    current_texts = []
                    current_tokens = 0

            current_texts.append(sentence)
            current_tokens += sentence_tokens

        if current_texts:
            chunks.append(
                self._create_chunk(
                    document=document,
                    text=" ".join(current_texts),
                    chunk_index=chunk_index,
                )
            )

        return chunks

    def _split_large_segment(
        self,
        segment: Segment,
        document: CanonicalDocument,
        start_index: int,
    ) -> list[Chunk]:
        """Split a large segment into multiple chunks."""
        chunks = []
        sentences = self._split_into_sentences(segment.text)

        current_texts: list[str] = []
        current_tokens = 0
        chunk_index = start_index

        # Estimate time per character for timestamp interpolation
        if segment.start_offset is not None and segment.end_offset is not None:
            total_chars = len(segment.text)
            duration = segment.end_offset - segment.start_offset
            ms_per_char = duration / max(total_chars, 1)
        else:
            ms_per_char = 0

        char_offset = 0

        for sentence in sentences:
            sentence_tokens = self._count_tokens(sentence)

            if current_tokens + sentence_tokens > self.max_tokens and current_texts:
                start_ms = (
                    segment.start_offset + int(char_offset * ms_per_char)
                    if segment.start_offset is not None
                    else None
                )
                text = " ".join(current_texts)
                end_ms = (
                    segment.start_offset + int((char_offset + len(text)) * ms_per_char)
                    if segment.start_offset is not None
                    else None
                )

                chunks.append(
                    self._create_chunk(
                        document=document,
                        text=text,
                        chunk_index=chunk_index,
                        start_offset=start_ms,
                        end_offset=end_ms,
                    )
                )
                chunk_index += 1
                char_offset += len(text) + 1

                current_texts = []
                current_tokens = 0

            current_texts.append(sentence)
            current_tokens += sentence_tokens

        if current_texts:
            start_ms = (
                segment.start_offset + int(char_offset * ms_per_char)
                if segment.start_offset is not None
                else None
            )
            chunks.append(
                self._create_chunk(
                    document=document,
                    text=" ".join(current_texts),
                    chunk_index=chunk_index,
                    start_offset=start_ms,
                    end_offset=segment.end_offset,
                )
            )

        return chunks

    def _create_chunk(
        self,
        document: CanonicalDocument,
        text: str,
        chunk_index: int,
        start_offset: Optional[int] = None,
        end_offset: Optional[int] = None,
    ) -> Chunk:
        """Create a Chunk from text and document metadata."""
        return Chunk(
            document_id=document.id,
            user_id=document.user_id,
            chunk_index=chunk_index,
            text=text,
            token_count=self._count_tokens(text),
            source_type=document.source_type,
            source_url=document.source_url,
            source_title=document.source_title,
            timestamp_start_ms=start_offset,
            timestamp_end_ms=end_offset,
        )

    def _count_tokens(self, text: str) -> int:
        """Count tokens in text using tiktoken."""
        return len(self.encoder.encode(text))

    def _get_overlap_text(self, texts: list[str]) -> str:
        """Get the overlap text from the end of the current chunk."""
        if not texts or self.overlap_tokens == 0:
            return ""

        # Work backwards through texts to get overlap
        overlap_texts = []
        overlap_token_count = 0

        for text in reversed(texts):
            text_tokens = self._count_tokens(text)
            if overlap_token_count + text_tokens <= self.overlap_tokens:
                overlap_texts.insert(0, text)
                overlap_token_count += text_tokens
            else:
                break

        return " ".join(overlap_texts)

    def _split_into_sentences(self, text: str) -> list[str]:
        """Split text into sentences at natural boundaries."""
        import re

        # Split on sentence-ending punctuation followed by space
        # But be careful with abbreviations like "Dr.", "Mr.", etc.
        sentence_pattern = r"(?<=[.!?])\s+(?=[A-Z])"
        sentences = re.split(sentence_pattern, text)

        # Filter empty strings and strip whitespace
        return [s.strip() for s in sentences if s.strip()]


