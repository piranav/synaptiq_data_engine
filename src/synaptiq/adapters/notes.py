"""
Notes adapter for user-created notes and markdown content.

Supports:
- Direct text/markdown content from API
- Local markdown files (Obsidian, etc.)
- Notion exports
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

import structlog

from synaptiq.adapters.base import BaseAdapter
from synaptiq.core.exceptions import AdapterError, ValidationError
from synaptiq.core.schemas import CanonicalDocument, Segment, SourceType

logger = structlog.get_logger(__name__)


class NotesAdapter(BaseAdapter):
    """
    Adapter for ingesting user notes and markdown content.
    
    Supports two modes:
    1. Direct content ingestion (from API - title + content)
    2. File path ingestion (local markdown files)
    
    Note: This adapter is not registered with the factory by default
    since it handles direct content or file paths, not URLs.
    """

    source_type = SourceType.NOTE

    @classmethod
    def can_handle(cls, url: str) -> bool:
        """
        Check if this is a local file path to a markdown file.
        """
        # Check if it's a file path (not a URL)
        if url.startswith(("http://", "https://")):
            return False

        path = Path(url)
        return path.suffix.lower() in (".md", ".markdown", ".txt")

    async def ingest_content(
        self,
        content: str,
        user_id: str,
        title: Optional[str] = None,
        note_id: Optional[str] = None,
    ) -> CanonicalDocument:
        """
        Ingest note content directly (not from a file).
        
        This is the primary method for API-based note ingestion.
        
        Args:
            content: The markdown/text content of the note
            user_id: User ID for multi-tenant isolation
            title: Optional title (extracted from content if not provided)
            note_id: Optional note ID for updates (generates new if not provided)
            
        Returns:
            CanonicalDocument with section segments
        """
        logger.info(
            "Ingesting note content",
            user_id=user_id,
            content_length=len(content),
            has_title=bool(title),
        )

        try:
            # Extract title from content if not provided
            if not title:
                title = self._extract_title_from_content(content)
            
            # Generate unique identifier for this note
            note_identifier = note_id or str(uuid4())
            
            # Extract frontmatter if present
            metadata = self._extract_frontmatter(content)
            
            # Remove frontmatter from content for processing
            clean_content = self._remove_frontmatter(content)
            
            # Build segments from content
            segments = self._build_segments(clean_content)

            return CanonicalDocument(
                id=note_identifier,
                user_id=user_id,
                source_type=SourceType.NOTE,
                source_url=f"note://{note_identifier}",
                source_title=title,
                source_metadata={
                    "note_id": note_identifier,
                    "frontmatter": metadata,
                    "word_count": len(clean_content.split()),
                    "is_direct_input": True,
                },
                raw_content=clean_content,
                content_segments=segments,
                created_at=datetime.utcnow(),
            )

        except Exception as e:
            logger.error("Error ingesting note content", error=str(e))
            raise AdapterError(
                message=f"Failed to ingest note content: {str(e)}",
                source_url="direct_input",
                adapter_type="notes",
                cause=e,
            )

    def _extract_title_from_content(self, content: str) -> str:
        """Extract title from frontmatter or first heading."""
        # Try frontmatter title first
        frontmatter = self._extract_frontmatter(content)
        if "title" in frontmatter:
            return frontmatter["title"]
        
        # Try first H1 heading
        match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        if match:
            return match.group(1).strip()
        
        # Fall back to first line or default
        first_line = content.strip().split("\n")[0][:50] if content.strip() else ""
        return first_line.strip() or "Untitled Note"

    async def ingest(self, path: str, user_id: str) -> CanonicalDocument:
        """
        Ingest a local markdown file.
        
        Args:
            path: Path to the markdown file
            user_id: User ID for multi-tenant isolation
            
        Returns:
            CanonicalDocument with section segments
        """
        file_path = Path(path)

        if not file_path.exists():
            raise ValidationError(
                message=f"File not found: {path}",
                details={"path": path},
            )

        if not file_path.is_file():
            raise ValidationError(
                message=f"Path is not a file: {path}",
                details={"path": path},
            )

        logger.info("Ingesting local note", path=path, user_id=user_id)

        try:
            content = file_path.read_text(encoding="utf-8")

            # Extract title from frontmatter or first heading
            title = self._extract_title(content, file_path)

            # Extract frontmatter metadata
            metadata = self._extract_frontmatter(content)

            # Remove frontmatter from content for processing
            clean_content = self._remove_frontmatter(content)

            # Build segments from content
            segments = self._build_segments(clean_content)

            # Get file timestamps
            stat = file_path.stat()

            return CanonicalDocument(
                user_id=user_id,
                source_type=SourceType.NOTE,
                source_url=f"file://{file_path.absolute()}",
                source_title=title,
                source_metadata={
                    "filename": file_path.name,
                    "directory": str(file_path.parent),
                    "frontmatter": metadata,
                    "word_count": len(clean_content.split()),
                },
                raw_content=clean_content,
                content_segments=segments,
                created_at=datetime.fromtimestamp(stat.st_ctime),
            )

        except UnicodeDecodeError as e:
            raise AdapterError(
                message=f"Could not decode file as UTF-8: {path}",
                source_url=path,
                adapter_type="notes",
                cause=e,
            )
        except Exception as e:
            logger.error("Error ingesting note", path=path, error=str(e))
            raise AdapterError(
                message=f"Failed to ingest note: {str(e)}",
                source_url=path,
                adapter_type="notes",
                cause=e,
            )

    def _extract_title(self, content: str, file_path: Path) -> str:
        """Extract title from frontmatter, first heading, or filename."""
        # Try frontmatter title
        frontmatter = self._extract_frontmatter(content)
        if "title" in frontmatter:
            return frontmatter["title"]

        # Try first H1 heading
        match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        if match:
            return match.group(1).strip()

        # Fall back to filename
        return file_path.stem.replace("-", " ").replace("_", " ").title()

    def _extract_frontmatter(self, content: str) -> dict:
        """Extract YAML frontmatter from content."""
        if not content.startswith("---"):
            return {}

        match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
        if not match:
            return {}

        frontmatter = {}
        for line in match.group(1).split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                frontmatter[key.strip()] = value.strip().strip('"\'')

        return frontmatter

    def _remove_frontmatter(self, content: str) -> str:
        """Remove YAML frontmatter from content."""
        if not content.startswith("---"):
            return content

        match = re.match(r"^---\n.*?\n---\n?", content, re.DOTALL)
        if match:
            return content[match.end():]

        return content

    def _build_segments(self, content: str) -> list[Segment]:
        """Build segments from markdown content, respecting headers."""
        segments = []
        char_offset = 0

        # Split by headers
        parts = re.split(r"(^#{1,6}\s+.+$)", content, flags=re.MULTILINE)

        current_text = ""
        current_type = "paragraph"

        for part in parts:
            if not part.strip():
                continue

            heading_match = re.match(r"^(#{1,6})\s+(.+)$", part)

            if heading_match:
                # Save previous segment
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

                level = len(heading_match.group(1))
                heading_text = heading_match.group(2).strip()

                segments.append(
                    Segment(
                        text=heading_text,
                        start_offset=char_offset,
                        end_offset=char_offset + len(part),
                        segment_type=f"heading_{level}",
                    )
                )
                char_offset += len(part)
                current_text = ""
                current_type = "paragraph"
            else:
                current_text += part

        # Last segment
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


