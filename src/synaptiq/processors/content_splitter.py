"""
Content splitter for multimodal note processing.

Identifies and separates different content types from notes:
- Text blocks
- Tables (markdown/HTML)
- Images (inline, URLs, base64)
- Code blocks
- Mermaid diagrams
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

import structlog

logger = structlog.get_logger(__name__)


class ContentType(Enum):
    """Types of content blocks in notes."""
    TEXT = "text"
    TABLE = "table"
    IMAGE = "image"
    CODE = "code"
    MERMAID = "mermaid"


@dataclass
class ContentBlock:
    """
    A block of content extracted from a note.
    
    Attributes:
        type: The type of content (text, table, image, etc.)
        content: The raw content string
        start_offset: Character offset where this block starts in source
        end_offset: Character offset where this block ends in source
        context_before: Text before this block (~200 chars)
        context_after: Text after this block (~200 chars)
        metadata: Type-specific metadata (language for code, etc.)
    """
    type: ContentType
    content: str
    start_offset: int
    end_offset: int
    context_before: str = ""
    context_after: str = ""
    metadata: dict = field(default_factory=dict)


class ContentSplitter:
    """
    Splits note content into typed blocks while preserving context.
    
    Handles:
    - Markdown tables (| header | header |...)
    - HTML tables (<table>...</table>)
    - Images (![]() syntax, <img> tags, base64)
    - Fenced code blocks (```language...```)
    - Mermaid diagrams (```mermaid...```)
    """
    
    # Context window size in characters
    CONTEXT_SIZE = 200
    
    # Regex patterns for content detection
    PATTERNS = {
        # Markdown fenced code blocks (including mermaid)
        "fenced_code": re.compile(
            r"```(\w*)\n(.*?)```",
            re.DOTALL
        ),
        # Markdown tables (at least 2 rows with |)
        "markdown_table": re.compile(
            r"(?:^\|.+\|$\n)+",
            re.MULTILINE
        ),
        # HTML tables
        "html_table": re.compile(
            r"<table[^>]*>.*?</table>",
            re.DOTALL | re.IGNORECASE
        ),
        # Markdown images
        "markdown_image": re.compile(
            r"!\[([^\]]*)\]\(([^)]+)\)"
        ),
        # HTML images
        "html_image": re.compile(
            r"<img[^>]+src=[\"']([^\"']+)[\"'][^>]*>",
            re.IGNORECASE
        ),
        # Base64 images
        "base64_image": re.compile(
            r"data:image/[^;]+;base64,[A-Za-z0-9+/=]+"
        ),
    }
    
    def __init__(self, context_size: int = 200):
        """
        Initialize the content splitter.
        
        Args:
            context_size: Number of characters to capture before/after blocks
        """
        self.context_size = context_size
    
    def split(self, content: str | list[dict]) -> list[ContentBlock]:
        """
        Split content into typed blocks.
        
        Args:
            content: Either raw markdown string or TipTap JSON content
            
        Returns:
            List of ContentBlock objects with context
        """
        # Convert TipTap JSON to markdown if needed
        if isinstance(content, list):
            text_content = self._tiptap_to_markdown(content)
        else:
            text_content = content
        
        if not text_content:
            return []
        
        blocks = []
        
        # Track which regions have been extracted
        extracted_regions: list[tuple[int, int, ContentBlock]] = []
        
        # 1. Extract code blocks first (they might contain table-like content)
        extracted_regions.extend(
            self._extract_code_blocks(text_content)
        )
        
        # 2. Extract tables
        extracted_regions.extend(
            self._extract_tables(text_content, extracted_regions)
        )
        
        # 3. Extract images
        extracted_regions.extend(
            self._extract_images(text_content, extracted_regions)
        )
        
        # Sort by position
        extracted_regions.sort(key=lambda x: x[0])
        
        # 4. Fill in text blocks between extracted regions
        all_blocks = self._fill_text_blocks(text_content, extracted_regions)
        
        # 5. Add context to non-text blocks
        self._add_context(text_content, all_blocks)
        
        logger.info(
            "Content split complete",
            total_blocks=len(all_blocks),
            text_blocks=sum(1 for b in all_blocks if b.type == ContentType.TEXT),
            table_blocks=sum(1 for b in all_blocks if b.type == ContentType.TABLE),
            image_blocks=sum(1 for b in all_blocks if b.type == ContentType.IMAGE),
            code_blocks=sum(1 for b in all_blocks if b.type == ContentType.CODE),
            mermaid_blocks=sum(1 for b in all_blocks if b.type == ContentType.MERMAID),
        )
        
        return all_blocks
    
    def _extract_code_blocks(
        self, content: str
    ) -> list[tuple[int, int, ContentBlock]]:
        """Extract fenced code blocks."""
        regions = []
        
        for match in self.PATTERNS["fenced_code"].finditer(content):
            language = match.group(1).lower() if match.group(1) else ""
            code_content = match.group(2)
            start = match.start()
            end = match.end()
            
            # Determine if it's mermaid or regular code
            if language == "mermaid":
                content_type = ContentType.MERMAID
            else:
                content_type = ContentType.CODE
            
            block = ContentBlock(
                type=content_type,
                content=code_content.strip(),
                start_offset=start,
                end_offset=end,
                metadata={
                    "language": language,
                    "raw_block": match.group(0),  # Include fences
                }
            )
            regions.append((start, end, block))
        
        return regions
    
    def _extract_tables(
        self, 
        content: str,
        existing_regions: list[tuple[int, int, ContentBlock]]
    ) -> list[tuple[int, int, ContentBlock]]:
        """Extract markdown and HTML tables."""
        regions = []
        
        # Markdown tables
        for match in self.PATTERNS["markdown_table"].finditer(content):
            start = match.start()
            end = match.end()
            
            # Skip if overlaps with existing region (e.g., inside code block)
            if self._overlaps(start, end, existing_regions):
                continue
            
            # Validate it's a proper table (has header separator)
            table_text = match.group(0)
            if not self._is_valid_markdown_table(table_text):
                continue
            
            block = ContentBlock(
                type=ContentType.TABLE,
                content=table_text.strip(),
                start_offset=start,
                end_offset=end,
                metadata={
                    "format": "markdown",
                    "row_count": len(table_text.strip().split("\n")),
                }
            )
            regions.append((start, end, block))
        
        # HTML tables
        for match in self.PATTERNS["html_table"].finditer(content):
            start = match.start()
            end = match.end()
            
            if self._overlaps(start, end, existing_regions):
                continue
            
            block = ContentBlock(
                type=ContentType.TABLE,
                content=match.group(0),
                start_offset=start,
                end_offset=end,
                metadata={"format": "html"}
            )
            regions.append((start, end, block))
        
        return regions
    
    def _extract_images(
        self,
        content: str,
        existing_regions: list[tuple[int, int, ContentBlock]]
    ) -> list[tuple[int, int, ContentBlock]]:
        """Extract image references."""
        regions = []
        
        # Markdown images
        for match in self.PATTERNS["markdown_image"].finditer(content):
            start = match.start()
            end = match.end()
            
            if self._overlaps(start, end, existing_regions):
                continue
            
            alt_text = match.group(1)
            image_url = match.group(2)
            
            block = ContentBlock(
                type=ContentType.IMAGE,
                content=match.group(0),
                start_offset=start,
                end_offset=end,
                metadata={
                    "format": "markdown",
                    "alt_text": alt_text,
                    "url": image_url,
                    "is_base64": image_url.startswith("data:"),
                }
            )
            regions.append((start, end, block))
        
        # HTML images
        for match in self.PATTERNS["html_image"].finditer(content):
            start = match.start()
            end = match.end()
            
            if self._overlaps(start, end, existing_regions):
                continue
            
            image_url = match.group(1)
            
            block = ContentBlock(
                type=ContentType.IMAGE,
                content=match.group(0),
                start_offset=start,
                end_offset=end,
                metadata={
                    "format": "html",
                    "url": image_url,
                    "is_base64": image_url.startswith("data:"),
                }
            )
            regions.append((start, end, block))
        
        return regions
    
    def _is_valid_markdown_table(self, table_text: str) -> bool:
        """
        Check if text is a valid markdown table.
        
        A valid table has:
        - At least 2 rows
        - A separator row with dashes (|---|---|)
        """
        lines = table_text.strip().split("\n")
        if len(lines) < 2:
            return False
        
        # Check for separator row (contains dashes)
        for line in lines:
            if re.match(r"^\|[\s\-:|]+\|$", line):
                return True
        
        return False
    
    def _overlaps(
        self,
        start: int,
        end: int,
        regions: list[tuple[int, int, ContentBlock]]
    ) -> bool:
        """Check if a region overlaps with existing regions."""
        for r_start, r_end, _ in regions:
            if start < r_end and end > r_start:
                return True
        return False
    
    def _fill_text_blocks(
        self,
        content: str,
        extracted_regions: list[tuple[int, int, ContentBlock]]
    ) -> list[ContentBlock]:
        """Fill gaps between extracted regions with text blocks."""
        all_blocks = []
        current_pos = 0
        
        for start, end, block in extracted_regions:
            # Add text block for gap before this region
            if current_pos < start:
                text_content = content[current_pos:start].strip()
                if text_content:
                    text_block = ContentBlock(
                        type=ContentType.TEXT,
                        content=text_content,
                        start_offset=current_pos,
                        end_offset=start,
                    )
                    all_blocks.append(text_block)
            
            # Add the extracted block
            all_blocks.append(block)
            current_pos = end
        
        # Add remaining text after last extracted region
        if current_pos < len(content):
            text_content = content[current_pos:].strip()
            if text_content:
                text_block = ContentBlock(
                    type=ContentType.TEXT,
                    content=text_content,
                    start_offset=current_pos,
                    end_offset=len(content),
                )
                all_blocks.append(text_block)
        
        return all_blocks
    
    def _add_context(
        self,
        content: str,
        blocks: list[ContentBlock]
    ) -> None:
        """Add context_before and context_after to non-text blocks."""
        for i, block in enumerate(blocks):
            if block.type == ContentType.TEXT:
                continue
            
            # Context before
            context_start = max(0, block.start_offset - self.context_size)
            context_before = content[context_start:block.start_offset].strip()
            
            # Try to start at a word boundary
            if context_start > 0 and not content[context_start - 1].isspace():
                first_space = context_before.find(" ")
                if first_space != -1:
                    context_before = context_before[first_space + 1:]
            
            block.context_before = context_before
            
            # Context after
            context_end = min(len(content), block.end_offset + self.context_size)
            context_after = content[block.end_offset:context_end].strip()
            
            # Try to end at a word boundary
            if context_end < len(content) and not content[context_end].isspace():
                last_space = context_after.rfind(" ")
                if last_space != -1:
                    context_after = context_after[:last_space]
            
            block.context_after = context_after
    
    def _tiptap_to_markdown(self, content: list[dict]) -> str:
        """
        Convert TipTap JSON content to markdown.
        
        This is a simplified converter for the most common node types.
        """
        lines = []
        
        for node in content:
            node_type = node.get("type", "")
            node_content = node.get("content", [])
            attrs = node.get("attrs", {})
            
            if node_type == "paragraph":
                text = self._extract_text_from_content(node_content)
                lines.append(text)
                lines.append("")  # Empty line after paragraph
            
            elif node_type == "heading":
                level = attrs.get("level", 1)
                text = self._extract_text_from_content(node_content)
                lines.append(f"{'#' * level} {text}")
                lines.append("")
            
            elif node_type == "codeBlock":
                language = attrs.get("language", "")
                text = self._extract_text_from_content(node_content)
                lines.append(f"```{language}")
                lines.append(text)
                lines.append("```")
                lines.append("")
            
            elif node_type == "bulletList":
                for item in node_content:
                    if item.get("type") == "listItem":
                        item_text = self._extract_text_from_content(
                            item.get("content", [])
                        )
                        lines.append(f"- {item_text}")
                lines.append("")
            
            elif node_type == "orderedList":
                for i, item in enumerate(node_content, 1):
                    if item.get("type") == "listItem":
                        item_text = self._extract_text_from_content(
                            item.get("content", [])
                        )
                        lines.append(f"{i}. {item_text}")
                lines.append("")
            
            elif node_type == "blockquote":
                text = self._extract_text_from_content(node_content)
                for line in text.split("\n"):
                    lines.append(f"> {line}")
                lines.append("")
            
            elif node_type == "table":
                lines.extend(self._table_to_markdown(node))
                lines.append("")
            
            elif node_type == "image":
                src = attrs.get("src", "")
                alt = attrs.get("alt", "")
                lines.append(f"![{alt}]({src})")
                lines.append("")
            
            elif node_type == "horizontalRule":
                lines.append("---")
                lines.append("")
        
        return "\n".join(lines)
    
    def _extract_text_from_content(self, content: list) -> str:
        """Extract plain text from TipTap content array."""
        texts = []
        
        for item in content:
            if isinstance(item, str):
                texts.append(item)
            elif isinstance(item, dict):
                if item.get("type") == "text":
                    texts.append(item.get("text", ""))
                elif "content" in item:
                    texts.append(
                        self._extract_text_from_content(item["content"])
                    )
        
        return "".join(texts)
    
    def _table_to_markdown(self, table_node: dict) -> list[str]:
        """Convert TipTap table node to markdown table."""
        lines = []
        rows = table_node.get("content", [])
        
        for i, row in enumerate(rows):
            if row.get("type") != "tableRow":
                continue
            
            cells = row.get("content", [])
            cell_texts = []
            
            for cell in cells:
                cell_type = cell.get("type", "")
                if cell_type in ("tableCell", "tableHeader"):
                    text = self._extract_text_from_content(
                        cell.get("content", [])
                    )
                    cell_texts.append(text)
            
            if cell_texts:
                lines.append("| " + " | ".join(cell_texts) + " |")
                
                # Add separator after header row
                if i == 0:
                    separator = "| " + " | ".join(["---"] * len(cell_texts)) + " |"
                    lines.append(separator)
        
        return lines
