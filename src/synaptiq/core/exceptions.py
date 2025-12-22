"""
Custom exceptions for the Synaptiq Data Engine.
Provides a clear hierarchy of errors for different pipeline stages.
"""

from typing import Any, Optional


class SynaptiqError(Exception):
    """Base exception for all Synaptiq errors."""

    def __init__(
        self,
        message: str,
        details: Optional[dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ):
        super().__init__(message)
        self.message = message
        self.details = details or {}
        self.cause = cause

    def __str__(self) -> str:
        if self.cause:
            return f"{self.message} (caused by: {self.cause})"
        return self.message


class ValidationError(SynaptiqError):
    """Raised when input validation fails."""

    pass


class AdapterError(SynaptiqError):
    """Raised when a source adapter fails to ingest content."""

    def __init__(
        self,
        message: str,
        source_url: Optional[str] = None,
        adapter_type: Optional[str] = None,
        **kwargs,
    ):
        details = kwargs.pop("details", {})
        details.update({
            "source_url": source_url,
            "adapter_type": adapter_type,
        })
        super().__init__(message, details=details, **kwargs)
        self.source_url = source_url
        self.adapter_type = adapter_type


class ProcessingError(SynaptiqError):
    """Raised when processing (chunking, embedding, etc.) fails."""

    def __init__(
        self,
        message: str,
        processor_name: Optional[str] = None,
        document_id: Optional[str] = None,
        **kwargs,
    ):
        details = kwargs.pop("details", {})
        details.update({
            "processor_name": processor_name,
            "document_id": document_id,
        })
        super().__init__(message, details=details, **kwargs)
        self.processor_name = processor_name
        self.document_id = document_id


class StorageError(SynaptiqError):
    """Raised when storage operations fail."""

    def __init__(
        self,
        message: str,
        store_type: Optional[str] = None,
        operation: Optional[str] = None,
        **kwargs,
    ):
        details = kwargs.pop("details", {})
        details.update({
            "store_type": store_type,
            "operation": operation,
        })
        super().__init__(message, details=details, **kwargs)
        self.store_type = store_type
        self.operation = operation


class ConfigurationError(SynaptiqError):
    """Raised when configuration is invalid or missing."""

    pass


class RateLimitError(SynaptiqError):
    """Raised when an API rate limit is hit."""

    def __init__(
        self,
        message: str,
        retry_after: Optional[int] = None,
        **kwargs,
    ):
        details = kwargs.pop("details", {})
        details["retry_after"] = retry_after
        super().__init__(message, details=details, **kwargs)
        self.retry_after = retry_after


