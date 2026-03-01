"""
YouTube adapter using SUPADATA for transcript extraction.
"""

import asyncio
from datetime import datetime
from typing import Any, Optional

import structlog
from supadata import Supadata
from supadata.errors import SupadataError

from config.settings import get_settings
from synaptiq.adapters.base import (
    AdapterFactory,
    BaseAdapter,
    extract_youtube_video_id,
    is_youtube_url,
)
from synaptiq.core.exceptions import AdapterError
from synaptiq.core.schemas import CanonicalDocument, Segment, SourceType

logger = structlog.get_logger(__name__)


@AdapterFactory.register
class YouTubeAdapter(BaseAdapter):
    """
    Adapter for ingesting YouTube video transcripts via SUPADATA.
    
    Extracts timestamped transcript segments for citation support.
    """

    source_type = SourceType.YOUTUBE

    def __init__(self):
        settings = get_settings()
        self.client = Supadata(api_key=settings.supadata_api_key)

    @classmethod
    def can_handle(cls, url: str) -> bool:
        """Check if this is a YouTube URL."""
        return is_youtube_url(url)

    async def ingest(self, url: str, user_id: str) -> CanonicalDocument:
        """
        Ingest a YouTube video transcript.
        
        Args:
            url: YouTube video URL
            user_id: User ID for multi-tenant isolation
            
        Returns:
            CanonicalDocument with timestamped segments
        """
        video_id = extract_youtube_video_id(url)
        if not video_id:
            raise AdapterError(
                message="Could not extract video ID from URL",
                source_url=url,
                adapter_type="youtube",
            )

        logger.info("Ingesting YouTube video", url=url, video_id=video_id, user_id=user_id)

        try:
            # Fetch transcript with timestamps (not plain text)
            transcript_response = await asyncio.to_thread(
                self._fetch_transcript, url
            )

            # Fetch video metadata
            metadata = await asyncio.to_thread(
                self._fetch_video_metadata, url
            )

            # Build segments from transcript
            segments = self._build_segments(transcript_response)

            # Build raw content from segments
            raw_content = " ".join(seg.text for seg in segments)

            return CanonicalDocument(
                user_id=user_id,
                source_type=SourceType.YOUTUBE,
                source_url=self._normalize_url(url, video_id),
                source_title=metadata.get("title", f"YouTube Video {video_id}"),
                source_metadata={
                    "video_id": video_id,
                    "channel": metadata.get("channel"),
                    "channel_id": metadata.get("channel_id"),
                    "description": metadata.get("description"),
                    "duration": metadata.get("duration"),
                    "view_count": metadata.get("view_count"),
                    "like_count": metadata.get("like_count"),
                    "comment_count": metadata.get("comment_count"),
                    "thumbnail_url": metadata.get("thumbnail_url"),
                    "language": transcript_response.get("lang", "en"),
                    "is_generated": transcript_response.get("is_generated", False),
                },
                raw_content=raw_content,
                content_segments=segments,
                created_at=metadata.get("published_at"),
            )

        except SupadataError as e:
            logger.error(
                "SUPADATA error fetching YouTube transcript",
                url=url,
                error_code=e.error,
                error_message=e.message,
            )
            raise AdapterError(
                message=f"Failed to fetch YouTube transcript: {e.message}",
                source_url=url,
                adapter_type="youtube",
                cause=e,
                details={"error_code": e.error, "details": e.details},
            )
        except Exception as e:
            logger.error("Unexpected error ingesting YouTube video", url=url, error=str(e))
            raise AdapterError(
                message=f"Unexpected error ingesting YouTube video: {str(e)}",
                source_url=url,
                adapter_type="youtube",
                cause=e,
            )

    def _fetch_transcript(self, url: str) -> dict[str, Any]:
        """Fetch transcript from SUPADATA (sync, run in thread)."""
        # Use text=False to get timestamped segments.
        # lang="en" requests English; if unavailable, API returns first available (see docs.supadata.ai).
        result = self.client.youtube.transcript(url, text=False, lang="en")
        
        # Convert to dict format
        return {
            "content": result.content if hasattr(result, "content") else [],
            "lang": getattr(result, "lang", "en"),
            "is_generated": getattr(result, "is_generated", False),
        }

    def _fetch_video_metadata(self, url: str) -> dict[str, Any]:
        """Fetch video metadata from SUPADATA unified metadata endpoint (sync, run in thread)."""
        try:
            import httpx
            from config.settings import get_settings
            settings = get_settings()
            
            # Use the unified metadata endpoint with URL-encoded url parameter
            response = httpx.get(
                "https://api.supadata.ai/v1/metadata",
                params={"url": url},
                headers={"x-api-key": settings.supadata_api_key},
                timeout=30,
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Map unified schema to our internal format
                author = data.get("author", {}) or {}
                stats = data.get("stats", {}) or {}
                media = data.get("media", {}) or {}
                additional = data.get("additionalData", {}) or {}
                
                return {
                    "title": data.get("title"),
                    "channel": author.get("displayName"),
                    "channel_id": additional.get("channelId"),
                    "description": data.get("description"),
                    "duration": media.get("duration"),
                    "view_count": stats.get("views"),
                    "like_count": stats.get("likes"),
                    "comment_count": stats.get("comments"),
                    "thumbnail_url": media.get("thumbnailUrl"),
                    "published_at": self._parse_datetime(data.get("createdAt")),
                }
            else:
                logger.warning("Metadata API returned non-200", status=response.status_code, url=url)
                return {}
                
        except Exception as e:
            logger.warning("Could not fetch video metadata", url=url, error=str(e))
            return {}

    def _build_segments(self, transcript_response: dict[str, Any]) -> list[Segment]:
        """Build Segment objects from transcript response."""
        segments = []
        content = transcript_response.get("content", [])

        for item in content:
            # SUPADATA returns segments with offset (ms) and duration (ms)
            # Note: values may be floats, convert to int
            if isinstance(item, dict):
                text = item.get("text", "")
                offset = int(item.get("offset", 0) or 0)
                duration = int(item.get("duration", 0) or 0)
            else:
                # Handle object attributes
                text = getattr(item, "text", "")
                offset = int(getattr(item, "offset", 0) or 0)
                duration = int(getattr(item, "duration", 0) or 0)

            if text.strip():
                segments.append(
                    Segment(
                        text=text.strip(),
                        start_offset=offset,
                        end_offset=offset + duration if duration else None,
                        segment_type="transcript_segment",
                        metadata={"lang": transcript_response.get("lang", "en")},
                    )
                )

        return segments

    def _normalize_url(self, url: str, video_id: str) -> str:
        """Normalize to standard YouTube watch URL."""
        return f"https://www.youtube.com/watch?v={video_id}"

    def _parse_datetime(self, value: Optional[str]) -> Optional[datetime]:
        """Parse datetime string to datetime object."""
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return None

