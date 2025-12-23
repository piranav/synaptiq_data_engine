"""
LLM-based concept conflict resolution and disambiguation.

Handles merging, linking, or separating concepts when the same term
appears with potentially different meanings across sources.
"""

from __future__ import annotations

import json
from enum import Enum
from typing import TYPE_CHECKING, Optional

import structlog
from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config.settings import get_settings
from synaptiq.core.exceptions import ProcessingError, RateLimitError
from synaptiq.ontology.namespaces import build_concept_uri

if TYPE_CHECKING:
    from synaptiq.storage.fuseki import FusekiStore

logger = structlog.get_logger(__name__)


class ConflictAction(str, Enum):
    """Possible actions for concept conflict resolution."""
    
    CREATE_NEW = "CREATE_NEW"  # Create a new concept
    MERGE_INTO = "MERGE_INTO"  # Merge with existing concept
    LINK_EXISTING = "LINK_EXISTING"  # Link to existing concept (exact match)


class ExistingConcept(BaseModel):
    """Represents an existing concept in the graph."""
    
    uri: str
    label: str
    alt_labels: list[str] = Field(default_factory=list)
    definition_text: Optional[str] = None
    source_context: Optional[str] = None


class ExtractedConcept(BaseModel):
    """Represents a newly extracted concept from content."""
    
    label: str
    alt_labels: list[str] = Field(default_factory=list)
    definition_text: Optional[str] = None
    source_chunk_id: str
    source_context: Optional[str] = None
    confidence: float = 1.0


class ConflictResolution(BaseModel):
    """Result of conflict resolution for a concept."""
    
    action: ConflictAction
    concept_uri: str = Field(
        ...,
        description="URI of the concept to use (new or existing)",
    )
    merge_target_uri: Optional[str] = Field(
        None,
        description="URI of existing concept to merge into (if action is MERGE_INTO)",
    )
    reasoning: Optional[str] = Field(
        None,
        description="LLM's reasoning for the decision",
    )


CONFLICT_RESOLUTION_SYSTEM_PROMPT = """You are a knowledge graph expert helping to resolve concept conflicts.

When a new concept is extracted from content, you need to decide if it should be:
1. CREATE_NEW: Created as a new concept (different meaning from existing)
2. MERGE_INTO: Merged with an existing concept (same meaning, enriches it)
3. LINK_EXISTING: Linked to an existing concept (exact match, no new info)

Consider:
- Semantic equivalence: Are the concepts talking about the same thing?
- Context: Does the context suggest the same or different usage?
- Definitions: Do the definitions align or conflict?
- Domain: Are they from the same domain/field?

Respond in JSON format:
{
    "action": "CREATE_NEW" | "MERGE_INTO" | "LINK_EXISTING",
    "merge_target_index": <index of existing concept to merge with, or null>,
    "reasoning": "<brief explanation>"
}
"""

CONFLICT_RESOLUTION_USER_PROMPT = """
New concept extracted:
- Label: {new_label}
- Alternative labels: {new_alt_labels}
- Definition: {new_definition}
- Context: {new_context}

Existing concepts in user's knowledge graph:
{existing_concepts}

Should the new concept be created separately, merged with an existing one, or linked as equivalent?
"""


class ConflictResolver:
    """
    LLM-based concept disambiguation and merging.
    
    Uses GPT to compare definitions and context to determine
    whether concepts should be merged, linked, or kept separate.
    """

    def __init__(
        self,
        fuseki_store: Optional[FusekiStore] = None,
        model: str = "gpt-4o-mini",
        similarity_threshold: float = 0.85,
    ):
        """
        Initialize the conflict resolver.
        
        Args:
            fuseki_store: FusekiStore instance for graph queries
            model: OpenAI model for conflict resolution
            similarity_threshold: Threshold for considering concepts similar
        """
        settings = get_settings()
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.fuseki = fuseki_store
        self.model = model
        self.similarity_threshold = similarity_threshold
        
        logger.info(
            "ConflictResolver initialized",
            model=self.model,
        )

    def set_fuseki_store(self, fuseki_store: FusekiStore) -> None:
        """Set the Fuseki store instance (for lazy initialization)."""
        self.fuseki = fuseki_store

    async def resolve_concept(
        self,
        user_id: str,
        new_concept: ExtractedConcept,
    ) -> ConflictResolution:
        """
        Resolve potential conflicts for a new concept.
        
        Flow:
        1. Check for exact label match -> LINK_EXISTING
        2. Find similar concepts by label
        3. If similar found, use LLM to decide merge/separate
        4. If no similar found -> CREATE_NEW
        
        Args:
            user_id: User identifier
            new_concept: The newly extracted concept
            
        Returns:
            ConflictResolution with action and target URIs
        """
        if not self.fuseki:
            raise ProcessingError(
                message="FusekiStore not initialized in ConflictResolver",
                document_id="",
            )
        
        logger.debug(
            "Resolving concept conflict",
            user_id=user_id,
            label=new_concept.label,
        )
        
        # Step 1: Check for exact match
        exact_match_uri = await self.fuseki.concept_exists(
            user_id,
            new_concept.label,
        )
        
        if exact_match_uri:
            logger.debug(
                "Exact match found",
                label=new_concept.label,
                existing_uri=exact_match_uri,
            )
            return ConflictResolution(
                action=ConflictAction.LINK_EXISTING,
                concept_uri=exact_match_uri,
                reasoning="Exact label match found in knowledge graph",
            )
        
        # Step 2: Find similar concepts
        similar_concepts = await self._find_similar_concepts(
            user_id,
            new_concept,
        )
        
        if not similar_concepts:
            # No similar concepts -> create new
            new_uri = build_concept_uri(user_id, new_concept.label)
            logger.debug(
                "No similar concepts, creating new",
                label=new_concept.label,
                new_uri=new_uri,
            )
            return ConflictResolution(
                action=ConflictAction.CREATE_NEW,
                concept_uri=new_uri,
                reasoning="No similar concepts found in knowledge graph",
            )
        
        # Step 3: Use LLM to decide
        resolution = await self._llm_resolve(
            user_id,
            new_concept,
            similar_concepts,
        )
        
        logger.info(
            "Conflict resolved",
            label=new_concept.label,
            action=resolution.action,
            reasoning=resolution.reasoning,
        )
        
        return resolution

    async def _find_similar_concepts(
        self,
        user_id: str,
        new_concept: ExtractedConcept,
    ) -> list[ExistingConcept]:
        """
        Find concepts that might be similar to the new concept.
        
        Args:
            user_id: User identifier
            new_concept: The new concept to compare
            
        Returns:
            List of potentially similar existing concepts
        """
        # Search by label fragments
        label_parts = new_concept.label.lower().split()
        similar_concepts = []
        seen_uris = set()
        
        for part in label_parts:
            if len(part) < 3:
                continue
            
            results = await self.fuseki.find_similar_concepts(
                user_id,
                part,
                limit=5,
            )
            
            for r in results:
                uri = r.get("concept")
                if uri and uri not in seen_uris:
                    seen_uris.add(uri)
                    
                    # Get full concept details
                    details = await self.fuseki.get_concept_with_definition(
                        user_id,
                        uri,
                    )
                    
                    if details:
                        similar_concepts.append(
                            ExistingConcept(
                                uri=uri,
                                label=details.get("label", ""),
                                definition_text=details.get("definitionText"),
                                source_context=details.get("sourceTitle"),
                            )
                        )
        
        # Also search alt labels
        for alt_label in new_concept.alt_labels:
            if len(alt_label) < 3:
                continue
            
            results = await self.fuseki.find_similar_concepts(
                user_id,
                alt_label,
                limit=3,
            )
            
            for r in results:
                uri = r.get("concept")
                if uri and uri not in seen_uris:
                    seen_uris.add(uri)
                    details = await self.fuseki.get_concept_with_definition(
                        user_id,
                        uri,
                    )
                    if details:
                        similar_concepts.append(
                            ExistingConcept(
                                uri=uri,
                                label=details.get("label", ""),
                                definition_text=details.get("definitionText"),
                            )
                        )
        
        return similar_concepts[:10]  # Limit to 10 candidates

    @retry(
        retry=retry_if_exception_type((RateLimitError,)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=60),
    )
    async def _llm_resolve(
        self,
        user_id: str,
        new_concept: ExtractedConcept,
        existing_concepts: list[ExistingConcept],
    ) -> ConflictResolution:
        """
        Use LLM to decide how to handle the concept conflict.
        
        Args:
            user_id: User identifier
            new_concept: The new concept
            existing_concepts: List of similar existing concepts
            
        Returns:
            ConflictResolution decision
        """
        # Format existing concepts for prompt
        existing_str = "\n".join(
            f"{i}. Label: {c.label}\n"
            f"   Definition: {c.definition_text or 'Not defined'}\n"
            f"   Context: {c.source_context or 'Unknown'}"
            for i, c in enumerate(existing_concepts)
        )
        
        user_prompt = CONFLICT_RESOLUTION_USER_PROMPT.format(
            new_label=new_concept.label,
            new_alt_labels=", ".join(new_concept.alt_labels) or "None",
            new_definition=new_concept.definition_text or "Not explicitly defined",
            new_context=new_concept.source_context or "Unknown",
            existing_concepts=existing_str,
        )
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": CONFLICT_RESOLUTION_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=500,
            )
            
            content = response.choices[0].message.content
            if not content:
                logger.warning("Empty response from LLM for conflict resolution")
                return self._create_new_resolution(user_id, new_concept)
            
            parsed = json.loads(content)
            action = parsed.get("action", "CREATE_NEW")
            merge_index = parsed.get("merge_target_index")
            reasoning = parsed.get("reasoning", "")
            
            if action == "CREATE_NEW":
                return ConflictResolution(
                    action=ConflictAction.CREATE_NEW,
                    concept_uri=build_concept_uri(user_id, new_concept.label),
                    reasoning=reasoning,
                )
            
            elif action == "MERGE_INTO" and merge_index is not None:
                if 0 <= merge_index < len(existing_concepts):
                    target = existing_concepts[merge_index]
                    return ConflictResolution(
                        action=ConflictAction.MERGE_INTO,
                        concept_uri=target.uri,
                        merge_target_uri=target.uri,
                        reasoning=reasoning,
                    )
                else:
                    logger.warning(
                        "Invalid merge index from LLM",
                        index=merge_index,
                        max_index=len(existing_concepts) - 1,
                    )
                    return self._create_new_resolution(user_id, new_concept, reasoning)
            
            elif action == "LINK_EXISTING" and merge_index is not None:
                if 0 <= merge_index < len(existing_concepts):
                    target = existing_concepts[merge_index]
                    return ConflictResolution(
                        action=ConflictAction.LINK_EXISTING,
                        concept_uri=target.uri,
                        reasoning=reasoning,
                    )
                else:
                    return self._create_new_resolution(user_id, new_concept, reasoning)
            
            else:
                return self._create_new_resolution(user_id, new_concept, reasoning)
                
        except json.JSONDecodeError as e:
            logger.error("Failed to parse LLM response", error=str(e))
            return self._create_new_resolution(user_id, new_concept)
            
        except Exception as e:
            error_message = str(e).lower()
            if "rate limit" in error_message:
                raise RateLimitError(
                    message="OpenAI rate limit exceeded",
                    retry_after=60,
                    cause=e,
                )
            logger.error("LLM conflict resolution failed", error=str(e))
            return self._create_new_resolution(user_id, new_concept)

    def _create_new_resolution(
        self,
        user_id: str,
        concept: ExtractedConcept,
        reasoning: Optional[str] = None,
    ) -> ConflictResolution:
        """Create a CREATE_NEW resolution as fallback."""
        return ConflictResolution(
            action=ConflictAction.CREATE_NEW,
            concept_uri=build_concept_uri(user_id, concept.label),
            reasoning=reasoning or "Fallback: creating new concept",
        )

    async def batch_resolve(
        self,
        user_id: str,
        concepts: list[ExtractedConcept],
    ) -> list[ConflictResolution]:
        """
        Resolve conflicts for multiple concepts.
        
        Processes concepts sequentially to handle dependencies
        (earlier resolutions may affect later ones).
        
        Args:
            user_id: User identifier
            concepts: List of extracted concepts
            
        Returns:
            List of resolutions
        """
        resolutions = []
        
        for concept in concepts:
            try:
                resolution = await self.resolve_concept(user_id, concept)
                resolutions.append(resolution)
            except Exception as e:
                logger.error(
                    "Failed to resolve concept",
                    label=concept.label,
                    error=str(e),
                )
                # Fallback to CREATE_NEW
                resolutions.append(
                    self._create_new_resolution(user_id, concept)
                )
        
        return resolutions

