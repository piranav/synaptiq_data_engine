"""
Core domain schemas for the Synaptiq Data Engine.
All source adapters normalize their output to these schemas.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class SourceType(str, Enum):
    """Supported content source types."""

    YOUTUBE = "youtube"
    WEB_ARTICLE = "web_article"
    NOTE = "note"
    TWITTER = "twitter"
    TIKTOK = "tiktok"
    PODCAST = "podcast"
    PDF = "pdf"


class Segment(BaseModel):
    """
    A natural segment of content from the source.
    
    For YouTube videos, this represents a timestamped transcript segment.
    For web articles, this might be a paragraph or section.
    """

    text: str = Field(..., description="The segment text content")
    start_offset: Optional[int] = Field(
        None,
        description="Start offset in milliseconds (video) or characters (text)",
    )
    end_offset: Optional[int] = Field(
        None,
        description="End offset in milliseconds (video) or characters (text)",
    )
    segment_type: Optional[str] = Field(
        None,
        description="Type of segment: paragraph, speaker_turn, heading, etc.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional segment-specific metadata",
    )

    @property
    def duration_ms(self) -> Optional[int]:
        """Get segment duration in milliseconds."""
        if self.start_offset is not None and self.end_offset is not None:
            return self.end_offset - self.start_offset
        return None


class CanonicalDocument(BaseModel):
    """
    Canonical representation of any ingested content.
    
    All source adapters normalize their output to this schema,
    enabling a unified processing pipeline regardless of source type.
    """

    # Identity
    id: str = Field(default_factory=lambda: str(uuid4()), description="Unique document ID")
    user_id: str = Field(..., description="User ID for multi-tenant isolation")

    # Source Information
    source_type: SourceType = Field(..., description="Type of content source")
    source_url: str = Field(..., description="Original URL or path")
    source_title: str = Field(..., description="Title of the content")
    source_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Source-specific metadata (channel, author, etc.)",
    )

    # Content
    raw_content: str = Field(..., description="Full text content")
    content_segments: list[Segment] = Field(
        default_factory=list,
        description="Pre-segmented content (if source has natural breaks)",
    )

    # Timestamps
    created_at: Optional[datetime] = Field(
        None,
        description="When the original content was created",
    )
    ingested_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When we processed this content",
    )

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }


class Chunk(BaseModel):
    """
    A processed chunk of content ready for embedding.
    
    Created by the SemanticChunker from CanonicalDocument segments.
    """

    # Identity
    id: str = Field(default_factory=lambda: str(uuid4()), description="Unique chunk ID")
    document_id: str = Field(..., description="Parent document ID")
    user_id: str = Field(..., description="User ID for multi-tenant isolation")
    chunk_index: int = Field(..., description="Position in the document")

    # Content
    text: str = Field(..., description="Chunk text content")
    token_count: int = Field(default=0, description="Number of tokens in chunk")

    # Source Citation
    source_type: SourceType = Field(..., description="Type of content source")
    source_url: str = Field(..., description="Original URL")
    source_title: str = Field(..., description="Title for citation")
    timestamp_start_ms: Optional[int] = Field(
        None,
        description="Start timestamp in milliseconds (for video)",
    )
    timestamp_end_ms: Optional[int] = Field(
        None,
        description="End timestamp in milliseconds (for video)",
    )

    # Extracted Metadata (populated by processors)
    concepts: list[str] = Field(
        default_factory=list,
        description="Extracted concepts/topics",
    )
    has_definition: bool = Field(
        default=False,
        description="Whether this chunk contains a definition",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional processor-extracted metadata",
    )

    @property
    def citation_url(self) -> str:
        """Generate a citation URL with timestamp if applicable."""
        if self.source_type == SourceType.YOUTUBE and self.timestamp_start_ms:
            seconds = self.timestamp_start_ms // 1000
            return f"{self.source_url}&t={seconds}s"
        return self.source_url


class ProcessedChunk(BaseModel):
    """
    A fully processed chunk with embedding, ready for storage.
    
    This is the final output of the processing pipeline,
    containing all information needed for Qdrant storage.
    """

    # Identity
    id: str = Field(..., description="Unique chunk ID (same as Chunk.id)")
    document_id: str = Field(..., description="Parent document ID")
    user_id: str = Field(..., description="User ID for filtering")
    chunk_index: int = Field(..., description="Position in document")

    # Vector
    vector: list[float] = Field(..., description="Embedding vector")

    # Content (for payload)
    text: str = Field(..., description="Chunk text for display")

    # Citation
    source_type: str = Field(..., description="Source type as string")
    source_url: str = Field(..., description="Original URL")
    source_title: str = Field(..., description="Title for citation")
    timestamp_start_ms: Optional[int] = Field(None, description="Video start time")
    timestamp_end_ms: Optional[int] = Field(None, description="Video end time")

    # Extracted Metadata
    concepts: list[str] = Field(default_factory=list, description="Extracted concepts")
    has_definition: bool = Field(default=False, description="Has definition flag")

    def to_qdrant_payload(self) -> dict[str, Any]:
        """Convert to Qdrant point payload format."""
        return {
            "document_id": self.document_id,
            "user_id": self.user_id,
            "chunk_index": self.chunk_index,
            "text": self.text,
            "source_type": self.source_type,
            "source_url": self.source_url,
            "source_title": self.source_title,
            "timestamp_start_ms": self.timestamp_start_ms,
            "timestamp_end_ms": self.timestamp_end_ms,
            "concepts": self.concepts,
            "has_definition": self.has_definition,
        }


class JobStatus(str, Enum):
    """Status of an async ingestion job."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Job(BaseModel):
    """
    Represents an async ingestion job.
    Stored in MongoDB for status tracking.
    """

    id: str = Field(default_factory=lambda: str(uuid4()), description="Job ID")
    user_id: str = Field(..., description="User who initiated the job")
    source_url: str = Field(..., description="URL being ingested")
    source_type: Optional[SourceType] = Field(None, description="Detected source type")
    status: JobStatus = Field(default=JobStatus.PENDING, description="Current status")
    document_id: Optional[str] = Field(None, description="Resulting document ID")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    chunks_processed: int = Field(default=0, description="Number of chunks processed")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = Field(None)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }


