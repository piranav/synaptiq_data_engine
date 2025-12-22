"""
Base adapter protocol and factory for source adapters.
"""

import re
from abc import ABC, abstractmethod
from typing import Optional, Type

from synaptiq.core.schemas import CanonicalDocument, SourceType
from synaptiq.core.exceptions import AdapterError, ValidationError


class BaseAdapter(ABC):
    """
    Abstract base class for source adapters.
    
    All source adapters must implement the ingest method to normalize
    content from their source into a CanonicalDocument.
    """

    source_type: SourceType

    @abstractmethod
    async def ingest(self, url: str, user_id: str) -> CanonicalDocument:
        """
        Ingest content from the source URL.
        
        Args:
            url: The source URL to ingest
            user_id: The user ID for multi-tenant isolation
            
        Returns:
            CanonicalDocument with normalized content
            
        Raises:
            AdapterError: If ingestion fails
            ValidationError: If URL is invalid for this adapter
        """
        pass

    @classmethod
    @abstractmethod
    def can_handle(cls, url: str) -> bool:
        """
        Check if this adapter can handle the given URL.
        
        Args:
            url: The URL to check
            
        Returns:
            True if this adapter can handle the URL
        """
        pass


class AdapterFactory:
    """
    Factory for creating the appropriate adapter based on URL.
    
    Uses a registry pattern to allow easy addition of new adapters.
    """

    _adapters: list[Type[BaseAdapter]] = []

    @classmethod
    def register(cls, adapter_class: Type[BaseAdapter]) -> Type[BaseAdapter]:
        """
        Register an adapter class with the factory.
        
        Can be used as a decorator:
            @AdapterFactory.register
            class MyAdapter(BaseAdapter):
                ...
        """
        if adapter_class not in cls._adapters:
            cls._adapters.append(adapter_class)
        return adapter_class

    @classmethod
    def get_adapter(cls, url: str) -> BaseAdapter:
        """
        Get the appropriate adapter for a URL.
        
        Args:
            url: The URL to find an adapter for
            
        Returns:
            An instance of the appropriate adapter
            
        Raises:
            ValidationError: If no adapter can handle the URL
        """
        for adapter_class in cls._adapters:
            if adapter_class.can_handle(url):
                return adapter_class()

        raise ValidationError(
            message=f"No adapter found for URL: {url}",
            details={"url": url, "registered_adapters": [a.__name__ for a in cls._adapters]},
        )

    @classmethod
    def detect_source_type(cls, url: str) -> Optional[SourceType]:
        """
        Detect the source type from a URL without creating an adapter.
        
        Args:
            url: The URL to analyze
            
        Returns:
            The detected SourceType or None
        """
        for adapter_class in cls._adapters:
            if adapter_class.can_handle(url):
                return adapter_class.source_type
        return None

    @classmethod
    def list_adapters(cls) -> list[str]:
        """List all registered adapter names."""
        return [a.__name__ for a in cls._adapters]


# URL pattern helpers
YOUTUBE_PATTERNS = [
    r"(?:https?://)?(?:www\.)?youtube\.com/watch\?v=[\w-]+",
    r"(?:https?://)?(?:www\.)?youtu\.be/[\w-]+",
    r"(?:https?://)?(?:www\.)?youtube\.com/shorts/[\w-]+",
]

WEB_ARTICLE_PATTERN = r"https?://(?!(?:www\.)?(?:youtube\.com|youtu\.be|twitter\.com|x\.com|tiktok\.com))[\w.-]+.*"


def is_youtube_url(url: str) -> bool:
    """Check if URL is a YouTube video URL."""
    return any(re.match(pattern, url, re.IGNORECASE) for pattern in YOUTUBE_PATTERNS)


def is_web_article_url(url: str) -> bool:
    """Check if URL is a general web article (not a known video/social platform)."""
    return bool(re.match(WEB_ARTICLE_PATTERN, url, re.IGNORECASE))


def extract_youtube_video_id(url: str) -> Optional[str]:
    """Extract video ID from various YouTube URL formats."""
    patterns = [
        r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([\w-]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, url, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


