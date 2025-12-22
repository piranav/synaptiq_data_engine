"""Core domain models and exceptions."""

from synaptiq.core.schemas import (
    CanonicalDocument,
    Chunk,
    Job,
    JobStatus,
    ProcessedChunk,
    Segment,
    SourceType,
)
from synaptiq.core.exceptions import (
    SynaptiqError,
    AdapterError,
    ConfigurationError,
    ProcessingError,
    RateLimitError,
    StorageError,
    ValidationError,
)

__all__ = [
    "CanonicalDocument",
    "Chunk",
    "Job",
    "JobStatus",
    "ProcessedChunk",
    "Segment",
    "SourceType",
    "SynaptiqError",
    "AdapterError",
    "ConfigurationError",
    "ProcessingError",
    "RateLimitError",
    "StorageError",
    "ValidationError",
]

