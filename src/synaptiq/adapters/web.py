"""
Web article adapter using SUPADATA for content extraction.
"""

import asyncio
import re
from datetime import datetime
from typing import Any, Optional
from urllib.parse import urlparse

import structlog
from supadata import Supadata
from supadata.errors import SupadataError

from config.settings import get_settings
from synaptiq.adapters.base import AdapterFactory, BaseAdapter, is_web_article_url
from synaptiq.core.exceptions import AdapterError
from synaptiq.core.schemas import CanonicalDocument, Segment, SourceType

logger = structlog.get_logger(__name__)


@AdapterFactory.register
class WebAdapter(BaseAdapter):
    """
    Adapter for ingesting web articles via SUPADATA.
    
    Extracts content as Markdown and segments by paragraphs/sections.
    """

    source_type = SourceType.WEB_ARTICLE

    def __init__(self):
        settings = get_settings()
        self.client = Supadata(api_key=settings.supadata_api_key)

    @classmethod
    def can_handle(cls, url: str) -> bool:
        """Check if this is a web article URL (not a known video platform)."""
        return is_web_article_url(url)

    async def ingest(self, url: str, user_id: str) -> CanonicalDocument:
        """
        Ingest a web article.
        
        Args:
            url: Web article URL
            user_id: User ID for multi-tenant isolation
            
        Returns:
            CanonicalDocument with paragraph segments
        """
        logger.info("Ingesting web article", url=url, user_id=user_id)

        try:
            # Fetch content via SUPADATA web scrape
            result = await asyncio.to_thread(self._fetch_content, url)

            content = result.get("content", "")
            title = result.get("title") or self._extract_title_from_url(url)

            # Build segments from markdown content
            segments = self._build_segments(content)

            return CanonicalDocument(
                user_id=user_id,
                source_type=SourceType.WEB_ARTICLE,
                source_url=url,
                source_title=title,
                source_metadata={
                    "domain": urlparse(url).netloc,
                    "description": result.get("description"),
                    "author": result.get("author"),
                    "published_date": result.get("published_date"),
                    "word_count": len(content.split()) if content else 0,
                },
                raw_content=content,
                content_segments=segments,
                created_at=self._parse_datetime(result.get("published_date")),
            )

        except SupadataError as e:
            logger.error(
                "SUPADATA error fetching web content",
                url=url,
                error_code=e.error,
                error_message=e.message,
            )
            raise AdapterError(
                message=f"Failed to fetch web content: {e.message}",
                source_url=url,
                adapter_type="web",
                cause=e,
                details={"error_code": e.error, "details": e.details},
            )
        except Exception as e:
            logger.error("Unexpected error ingesting web article", url=url, error=str(e))
            raise AdapterError(
                message=f"Unexpected error ingesting web article: {str(e)}",
                source_url=url,
                adapter_type="web",
                cause=e,
            )

    def _fetch_content(self, url: str) -> dict[str, Any]:
        """Fetch content from SUPADATA (sync, run in thread)."""
        # Note: url is positional argument in SUPADATA SDK
        result = self.client.web.scrape(url)

        return {
            "content": getattr(result, "content", ""),
            "title": getattr(result, "name", None) or getattr(result, "title", None),
            "description": getattr(result, "description", None),
            "author": getattr(result, "author", None),
            "published_date": getattr(result, "published_date", None),
        }

    def _build_segments(self, content: str) -> list[Segment]:
        """
        Build segments from Markdown content.
        
        Splits by:
        1. Headings (# ## ### etc.)
        2. Double newlines (paragraph breaks)
        """
        if not content:
            return []

        segments = []
        char_offset = 0

        # Split by headings and paragraph breaks
        # Pattern matches: heading lines OR double newlines
        parts = re.split(r"((?:^|\n)#{1,6}\s+[^\n]+)|(\n\n+)", content)

        current_text = ""
        current_type = "paragraph"

        for part in parts:
            if part is None or part == "":
                continue

            # Check if this is a heading
            heading_match = re.match(r"(?:^|\n)(#{1,6})\s+(.+)", part)
            if heading_match:
                # Save previous segment if exists
                if current_text.strip():
                    segments.append(
                        Segment(
                            text=current_text.strip(),
                            start_offset=char_offset,
                            end_offset=char_offset + len(current_text),
                            segment_type=current_type,
                        )
                    )
                    char_offset += len(current_text)

                # Start new heading segment
                level = len(heading_match.group(1))
                current_text = heading_match.group(2).strip()
                current_type = f"heading_{level}"

            elif part.strip():
                # Regular content
                if current_text:
                    current_text += " " + part.strip()
                else:
                    current_text = part.strip()
                    current_type = "paragraph"

            # Handle paragraph break (double newline)
            elif "\n\n" in part and current_text.strip():
                segments.append(
                    Segment(
                        text=current_text.strip(),
                        start_offset=char_offset,
                        end_offset=char_offset + len(current_text),
                        segment_type=current_type,
                    )
                )
                char_offset += len(current_text) + len(part)
                current_text = ""
                current_type = "paragraph"

        # Don't forget the last segment
        if current_text.strip():
            segments.append(
                Segment(
                    text=current_text.strip(),
                    start_offset=char_offset,
                    end_offset=char_offset + len(current_text),
                    segment_type=current_type,
                )
            )

        return segments

    def _extract_title_from_url(self, url: str) -> str:
        """Extract a readable title from URL as fallback."""
        parsed = urlparse(url)
        path = parsed.path.strip("/")

        if path:
            # Use last path segment, clean up
            title = path.split("/")[-1]
            title = re.sub(r"[-_]", " ", title)
            title = re.sub(r"\.\w+$", "", title)  # Remove extension
            return title.title()

        return parsed.netloc

    def _parse_datetime(self, value: Optional[str]) -> Optional[datetime]:
        """Parse datetime string to datetime object."""
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return None

