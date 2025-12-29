"""
Context linker for enriching artifacts with surrounding text.

Ensures that extracted artifacts (tables, images, code) maintain
their semantic context from the source document.
"""

import re
from dataclasses import dataclass
from typing import Any, Optional

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class ContextEnrichedArtifact:
    """An artifact enriched with document context."""
    artifact_id: str
    artifact_type: str
    description: str
    context_before: str
    context_after: str
    section_title: Optional[str]
    document_title: str
    combined_text_for_embedding: str
    position_in_source: int
    
    # Type-specific data
    raw_content: str
    extraction_data: dict


class ContextLinker:
    """
    Links artifacts to their surrounding context.
    
    Enriches each artifact with:
    - Text before and after
    - Section/heading context
    - Document title
    - Combined text optimized for embedding
    """
    
    # Heading patterns to extract section context
    HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
    
    def __init__(self, context_size: int = 200):
        """
        Initialize the context linker.
        
        Args:
            context_size: Characters of context to include before/after
        """
        self.context_size = context_size
    
    def link_context(
        self,
        artifact_id: str,
        artifact_type: str,
        description: str,
        raw_content: str,
        extraction_data: dict,
        position: int,
        full_content: str,
        document_title: str,
    ) -> ContextEnrichedArtifact:
        """
        Enrich an artifact with document context.
        
        Args:
            artifact_id: Unique artifact identifier
            artifact_type: Type of artifact (table, image, code, mermaid)
            description: LLM-generated description
            raw_content: Raw artifact content
            extraction_data: Type-specific extraction data
            position: Character offset in source
            full_content: Full document content
            document_title: Title of source document
            
        Returns:
            ContextEnrichedArtifact with full context
        """
        # Extract context before
        context_before = self._extract_context_before(full_content, position)
        
        # Find artifact end position
        end_position = position + len(raw_content)
        
        # Extract context after
        context_after = self._extract_context_after(full_content, end_position)
        
        # Find section title
        section_title = self._find_section_title(full_content, position)
        
        # Build combined text for embedding
        combined_text = self._build_combined_text(
            artifact_type=artifact_type,
            description=description,
            context_before=context_before,
            context_after=context_after,
            section_title=section_title,
            document_title=document_title,
        )
        
        logger.debug(
            "Context linked",
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            section=section_title,
            combined_length=len(combined_text),
        )
        
        return ContextEnrichedArtifact(
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            description=description,
            context_before=context_before,
            context_after=context_after,
            section_title=section_title,
            document_title=document_title,
            combined_text_for_embedding=combined_text,
            position_in_source=position,
            raw_content=raw_content,
            extraction_data=extraction_data,
        )
    
    def _extract_context_before(self, content: str, position: int) -> str:
        """Extract text before the artifact position."""
        start = max(0, position - self.context_size)
        context = content[start:position].strip()
        
        # Try to start at a word/sentence boundary
        if start > 0:
            # Look for sentence boundary
            sentence_match = re.search(r'[.!?]\s+', context)
            if sentence_match and sentence_match.end() < len(context) // 2:
                context = context[sentence_match.end():]
            else:
                # Fall back to word boundary
                first_space = context.find(' ')
                if first_space != -1 and first_space < len(context) // 4:
                    context = context[first_space + 1:]
        
        return context
    
    def _extract_context_after(self, content: str, position: int) -> str:
        """Extract text after the artifact position."""
        end = min(len(content), position + self.context_size)
        context = content[position:end].strip()
        
        # Try to end at a word/sentence boundary
        if end < len(content):
            # Look for sentence boundary
            sentence_match = re.search(r'[.!?]\s+', context[::-1])
            if sentence_match and sentence_match.start() < len(context) // 2:
                last_period = len(context) - sentence_match.end() + 1
                context = context[:last_period]
            else:
                # Fall back to word boundary
                last_space = context.rfind(' ')
                if last_space != -1 and last_space > len(context) * 3 // 4:
                    context = context[:last_space]
        
        return context
    
    def _find_section_title(self, content: str, position: int) -> Optional[str]:
        """Find the section heading that contains this position."""
        # Search for headings before this position
        text_before = content[:position]
        
        matches = list(self.HEADING_PATTERN.finditer(text_before))
        
        if matches:
            # Return the most recent (closest) heading
            last_match = matches[-1]
            return last_match.group(2).strip()
        
        return None
    
    def _build_combined_text(
        self,
        artifact_type: str,
        description: str,
        context_before: str,
        context_after: str,
        section_title: Optional[str],
        document_title: str,
    ) -> str:
        """
        Build optimized text for embedding.
        
        Format:
        [Document: Title | Section: Section Name]
        Context before...
        [ARTIFACT_TYPE: Description]
        Context after...
        """
        parts = []
        
        # Document/section header
        if section_title:
            parts.append(f"[Document: {document_title} | Section: {section_title}]")
        else:
            parts.append(f"[Document: {document_title}]")
        
        # Context before
        if context_before:
            parts.append(context_before)
        
        # Artifact with description
        type_label = artifact_type.upper()
        parts.append(f"[{type_label}: {description}]")
        
        # Context after
        if context_after:
            parts.append(context_after)
        
        return " ".join(parts)
    
    def batch_link(
        self,
        artifacts: list[dict],
        full_content: str,
        document_title: str,
    ) -> list[ContextEnrichedArtifact]:
        """
        Link context for multiple artifacts.
        
        Args:
            artifacts: List of artifact dicts with required fields
            full_content: Full document content
            document_title: Document title
            
        Returns:
            List of ContextEnrichedArtifact
        """
        enriched = []
        
        for artifact in artifacts:
            enriched_artifact = self.link_context(
                artifact_id=artifact["id"],
                artifact_type=artifact["type"],
                description=artifact["description"],
                raw_content=artifact["raw_content"],
                extraction_data=artifact.get("extraction_data", {}),
                position=artifact["position"],
                full_content=full_content,
                document_title=document_title,
            )
            enriched.append(enriched_artifact)
        
        return enriched
