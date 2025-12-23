"""
Ontology writer processor for persisting extracted concepts and relationships
to the RDF graph store.

This processor runs after ConceptExtractor and writes the extracted
concepts, definitions, and relationships to Apache Fuseki.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional

import structlog

from synaptiq.core.schemas import Chunk
from synaptiq.ontology.namespaces import (
    SYNAPTIQ,
    RDF,
    build_chunk_uri,
    build_concept_uri,
    build_definition_uri,
    build_source_uri,
    get_relationship_uri,
    get_source_class_uri,
    slugify,
)
from synaptiq.processors.base import BaseProcessor

if TYPE_CHECKING:
    from synaptiq.ontology.conflict_resolver import (
        ConflictAction,
        ConflictResolver,
        ExtractedConcept,
    )
    from synaptiq.storage.fuseki import FusekiStore

logger = structlog.get_logger(__name__)


class OntologyWriter(BaseProcessor):
    """
    Writes extracted concepts and relationships to the graph store.
    
    Flow:
    1. Collect all concepts and relationships from chunks
    2. For each concept, run conflict resolution
    3. Build RDF triples for concepts, definitions, relationships
    4. Batch insert into user's named graph
    5. Return chunks unchanged (passthrough)
    
    Features:
    - LLM-based conflict resolution for concept merging
    - Provenance tracking (which chunk defined/mentioned concepts)
    - Relationship linking between concepts
    - Source metadata persistence
    """

    def __init__(
        self,
        fuseki_store: Optional[FusekiStore] = None,
        conflict_resolver: Optional[ConflictResolver] = None,
        write_sources: bool = True,
        write_chunks: bool = True,
        confidence_threshold: float = 0.5,
    ):
        """
        Initialize the ontology writer.
        
        Args:
            fuseki_store: FusekiStore instance (lazy initialized if None)
            conflict_resolver: ConflictResolver instance (lazy initialized if None)
            write_sources: Whether to write source metadata to graph
            write_chunks: Whether to write chunk metadata to graph
            confidence_threshold: Minimum confidence for relationships
        """
        self._fuseki: Optional[FusekiStore] = fuseki_store
        self._resolver: Optional[ConflictResolver] = conflict_resolver
        self.write_sources = write_sources
        self.write_chunks = write_chunks
        self.confidence_threshold = confidence_threshold
        
        # Track processed concepts to avoid duplicates within a batch
        self._concept_cache: dict[str, str] = {}  # label -> uri
        
        logger.info(
            "OntologyWriter initialized",
            write_sources=write_sources,
            write_chunks=write_chunks,
            confidence_threshold=confidence_threshold,
        )

    @property
    def fuseki(self) -> FusekiStore:
        """Lazy-initialize FusekiStore."""
        if self._fuseki is None:
            from synaptiq.storage.fuseki import FusekiStore
            self._fuseki = FusekiStore()
        return self._fuseki

    @property
    def resolver(self) -> ConflictResolver:
        """Lazy-initialize ConflictResolver."""
        if self._resolver is None:
            from synaptiq.ontology.conflict_resolver import ConflictResolver
            self._resolver = ConflictResolver(fuseki_store=self.fuseki)
        else:
            # Ensure resolver has fuseki store
            self._resolver.set_fuseki_store(self.fuseki)
        return self._resolver

    async def process(self, chunks: list[Chunk]) -> list[Chunk]:
        """
        Process chunks and write ontology data to graph store.
        
        Args:
            chunks: Input chunks with extracted concepts and relationships
            
        Returns:
            Chunks unchanged (passthrough processor)
        """
        if not chunks:
            return chunks

        logger.info("OntologyWriter processing", chunk_count=len(chunks))
        
        # Clear concept cache for this batch
        self._concept_cache.clear()
        
        # Get user_id from first chunk (all should have same user_id)
        user_id = chunks[0].user_id
        
        try:
            # Ensure dataset and user graph exist
            await self.fuseki.ensure_dataset()
            
            if not await self.fuseki.user_graph_exists(user_id):
                await self.fuseki.create_user_graph(user_id)
                logger.info("Created user graph", user_id=user_id)
            
            # Collect all triples to insert
            all_triples: list[dict[str, Any]] = []
            
            # Track which sources we've already written
            written_sources: set[str] = set()
            
            for chunk in chunks:
                # Write source (if not already written)
                if self.write_sources and chunk.source_url not in written_sources:
                    source_triples = self._build_source_triples(chunk)
                    all_triples.extend(source_triples)
                    written_sources.add(chunk.source_url)
                
                # Write chunk
                if self.write_chunks:
                    chunk_triples = self._build_chunk_triples(chunk)
                    all_triples.extend(chunk_triples)
                
                # Process concepts
                concepts_triples = await self._process_chunk_concepts(
                    chunk,
                    user_id,
                )
                all_triples.extend(concepts_triples)
                
                # Process relationships
                relationship_triples = await self._process_chunk_relationships(
                    chunk,
                    user_id,
                )
                all_triples.extend(relationship_triples)
            
            # Batch insert all triples
            if all_triples:
                count = await self.fuseki.insert_triples(user_id, all_triples)
                logger.info(
                    "OntologyWriter complete",
                    user_id=user_id,
                    chunk_count=len(chunks),
                    triple_count=count,
                    concept_count=len(self._concept_cache),
                )
            else:
                logger.info(
                    "OntologyWriter complete (no triples to write)",
                    user_id=user_id,
                    chunk_count=len(chunks),
                )
            
        except Exception as e:
            logger.error(
                "OntologyWriter failed",
                error=str(e),
                user_id=user_id,
            )
            # Don't fail the pipeline, just log the error
            # The chunks will still proceed to embedding
        
        return chunks

    def _build_source_triples(self, chunk: Chunk) -> list[dict[str, Any]]:
        """Build RDF triples for a source."""
        # Use document_id as source identifier
        source_uri = build_source_uri(chunk.document_id)
        source_class = get_source_class_uri(chunk.source_type.value)
        now = datetime.now(timezone.utc).isoformat()
        
        triples = [
            # Type
            {
                "subject": source_uri,
                "predicate": RDF.term("type"),
                "object": source_class,
                "is_literal": False,
            },
            # Also type as generic Source
            {
                "subject": source_uri,
                "predicate": RDF.term("type"),
                "object": SYNAPTIQ.term("Source"),
                "is_literal": False,
            },
            # Properties
            {
                "subject": source_uri,
                "predicate": SYNAPTIQ.term("sourceUrl"),
                "object": chunk.source_url,
                "is_literal": True,
            },
            {
                "subject": source_uri,
                "predicate": SYNAPTIQ.term("sourceTitle"),
                "object": chunk.source_title,
                "is_literal": True,
            },
            {
                "subject": source_uri,
                "predicate": SYNAPTIQ.term("sourceType"),
                "object": chunk.source_type.value,
                "is_literal": True,
            },
            {
                "subject": source_uri,
                "predicate": SYNAPTIQ.term("documentId"),
                "object": chunk.document_id,
                "is_literal": True,
            },
            {
                "subject": source_uri,
                "predicate": SYNAPTIQ.term("userId"),
                "object": chunk.user_id,
                "is_literal": True,
            },
            {
                "subject": source_uri,
                "predicate": SYNAPTIQ.term("createdAt"),
                "object": now,
                "is_literal": True,
            },
        ]
        
        return triples

    def _build_chunk_triples(self, chunk: Chunk) -> list[dict[str, Any]]:
        """Build RDF triples for a chunk."""
        chunk_uri = build_chunk_uri(chunk.id)
        source_uri = build_source_uri(chunk.document_id)
        now = datetime.now(timezone.utc).isoformat()
        
        triples = [
            # Type
            {
                "subject": chunk_uri,
                "predicate": RDF.term("type"),
                "object": SYNAPTIQ.term("Chunk"),
                "is_literal": False,
            },
            # Properties
            {
                "subject": chunk_uri,
                "predicate": SYNAPTIQ.term("chunkText"),
                "object": chunk.text[:1000],  # Truncate for graph storage
                "is_literal": True,
            },
            {
                "subject": chunk_uri,
                "predicate": SYNAPTIQ.term("chunkIndex"),
                "object": chunk.chunk_index,
                "is_literal": True,
            },
            {
                "subject": chunk_uri,
                "predicate": SYNAPTIQ.term("vectorId"),
                "object": chunk.id,
                "is_literal": True,
            },
            {
                "subject": chunk_uri,
                "predicate": SYNAPTIQ.term("documentId"),
                "object": chunk.document_id,
                "is_literal": True,
            },
            {
                "subject": chunk_uri,
                "predicate": SYNAPTIQ.term("userId"),
                "object": chunk.user_id,
                "is_literal": True,
            },
            {
                "subject": chunk_uri,
                "predicate": SYNAPTIQ.term("createdAt"),
                "object": now,
                "is_literal": True,
            },
            # Link to source
            {
                "subject": chunk_uri,
                "predicate": SYNAPTIQ.term("derivedFrom"),
                "object": source_uri,
                "is_literal": False,
            },
        ]
        
        # Add timestamps if present
        if chunk.timestamp_start_ms is not None:
            triples.append({
                "subject": chunk_uri,
                "predicate": SYNAPTIQ.term("timestampStart"),
                "object": chunk.timestamp_start_ms,
                "is_literal": True,
            })
        
        if chunk.timestamp_end_ms is not None:
            triples.append({
                "subject": chunk_uri,
                "predicate": SYNAPTIQ.term("timestampEnd"),
                "object": chunk.timestamp_end_ms,
                "is_literal": True,
            })
        
        return triples

    async def _process_chunk_concepts(
        self,
        chunk: Chunk,
        user_id: str,
    ) -> list[dict[str, Any]]:
        """Process concepts from a chunk and build triples."""
        from synaptiq.ontology.conflict_resolver import ConflictAction, ExtractedConcept
        
        triples: list[dict[str, Any]] = []
        chunk_uri = build_chunk_uri(chunk.id)
        source_uri = build_source_uri(chunk.document_id)
        now = datetime.now(timezone.utc).isoformat()
        
        # Get defined concept and definition text
        defined_concept = chunk.metadata.get("defined_concept")
        definition_text = chunk.metadata.get("definition_text")
        
        for concept_label in chunk.concepts:
            concept_label_lower = concept_label.lower().strip()
            if not concept_label_lower:
                continue
            
            # Check cache first
            if concept_label_lower in self._concept_cache:
                concept_uri = self._concept_cache[concept_label_lower]
            else:
                # Run conflict resolution
                extracted = ExtractedConcept(
                    label=concept_label_lower,
                    alt_labels=[],
                    definition_text=definition_text if defined_concept and defined_concept.lower() == concept_label_lower else None,
                    source_chunk_id=chunk.id,
                    source_context=chunk.source_title,
                    confidence=1.0,
                )
                
                try:
                    resolution = await self.resolver.resolve_concept(
                        user_id,
                        extracted,
                    )
                    concept_uri = resolution.concept_uri
                    
                    # If creating new concept, add creation triples
                    if resolution.action == ConflictAction.CREATE_NEW:
                        triples.extend(self._build_concept_creation_triples(
                            concept_uri,
                            concept_label_lower,
                            source_uri,
                            now,
                        ))
                    
                except Exception as e:
                    logger.warning(
                        "Conflict resolution failed, creating new concept",
                        label=concept_label_lower,
                        error=str(e),
                    )
                    # Fallback: create new concept
                    concept_uri = build_concept_uri(user_id, concept_label_lower)
                    triples.extend(self._build_concept_creation_triples(
                        concept_uri,
                        concept_label_lower,
                        source_uri,
                        now,
                    ))
                
                # Cache the concept
                self._concept_cache[concept_label_lower] = concept_uri
            
            # Add mention/definition link
            if defined_concept and defined_concept.lower() == concept_label_lower:
                # This concept is defined in this chunk
                triples.append({
                    "subject": concept_uri,
                    "predicate": SYNAPTIQ.term("definedIn"),
                    "object": chunk_uri,
                    "is_literal": False,
                })
                
                # Create definition entity if we have definition text
                if definition_text:
                    def_uri = build_definition_uri(user_id)
                    triples.extend([
                        {
                            "subject": def_uri,
                            "predicate": RDF.term("type"),
                            "object": SYNAPTIQ.term("Definition"),
                            "is_literal": False,
                        },
                        {
                            "subject": def_uri,
                            "predicate": SYNAPTIQ.term("definitionText"),
                            "object": definition_text,
                            "is_literal": True,
                        },
                        {
                            "subject": def_uri,
                            "predicate": SYNAPTIQ.term("extractedFrom"),
                            "object": chunk_uri,
                            "is_literal": False,
                        },
                        {
                            "subject": def_uri,
                            "predicate": SYNAPTIQ.term("createdAt"),
                            "object": now,
                            "is_literal": True,
                        },
                        {
                            "subject": concept_uri,
                            "predicate": SYNAPTIQ.term("hasDefinition"),
                            "object": def_uri,
                            "is_literal": False,
                        },
                    ])
            else:
                # This concept is mentioned (not defined) in this chunk
                triples.append({
                    "subject": concept_uri,
                    "predicate": SYNAPTIQ.term("mentionedIn"),
                    "object": chunk_uri,
                    "is_literal": False,
                })
        
        return triples

    def _build_concept_creation_triples(
        self,
        concept_uri: str,
        label: str,
        source_uri: str,
        now: str,
    ) -> list[dict[str, Any]]:
        """Build triples for creating a new concept."""
        return [
            {
                "subject": concept_uri,
                "predicate": RDF.term("type"),
                "object": SYNAPTIQ.term("Concept"),
                "is_literal": False,
            },
            {
                "subject": concept_uri,
                "predicate": SYNAPTIQ.term("label"),
                "object": label,
                "is_literal": True,
            },
            {
                "subject": concept_uri,
                "predicate": SYNAPTIQ.term("slug"),
                "object": slugify(label),
                "is_literal": True,
            },
            {
                "subject": concept_uri,
                "predicate": SYNAPTIQ.term("firstLearnedFrom"),
                "object": source_uri,
                "is_literal": False,
            },
            {
                "subject": concept_uri,
                "predicate": SYNAPTIQ.term("createdAt"),
                "object": now,
                "is_literal": True,
            },
        ]

    async def _process_chunk_relationships(
        self,
        chunk: Chunk,
        user_id: str,
    ) -> list[dict[str, Any]]:
        """Process relationships from a chunk and build triples."""
        triples: list[dict[str, Any]] = []
        
        relationships = chunk.metadata.get("relationships", [])
        if not relationships:
            return triples
        
        for rel in relationships:
            # Skip low-confidence relationships
            confidence = rel.get("confidence", 1.0)
            if confidence < self.confidence_threshold:
                continue
            
            source_label = rel.get("source_concept", "").lower().strip()
            target_label = rel.get("target_concept", "").lower().strip()
            relation_type = rel.get("relation_type", "related_to")
            
            if not source_label or not target_label:
                continue
            
            # Get or resolve concept URIs
            source_uri = self._concept_cache.get(source_label)
            target_uri = self._concept_cache.get(target_label)
            
            if not source_uri:
                # Try to find existing or create new
                existing = await self.fuseki.concept_exists(user_id, source_label)
                if existing:
                    source_uri = existing
                else:
                    source_uri = build_concept_uri(user_id, source_label)
                    # Note: concept will be created if it appears in chunk.concepts
                self._concept_cache[source_label] = source_uri
            
            if not target_uri:
                existing = await self.fuseki.concept_exists(user_id, target_label)
                if existing:
                    target_uri = existing
                else:
                    target_uri = build_concept_uri(user_id, target_label)
                self._concept_cache[target_label] = target_uri
            
            # Get relationship predicate URI
            predicate_uri = get_relationship_uri(relation_type)
            
            # Add relationship triple
            triples.append({
                "subject": source_uri,
                "predicate": predicate_uri,
                "object": target_uri,
                "is_literal": False,
            })
            
            logger.debug(
                "Added relationship",
                source=source_label,
                relation=relation_type,
                target=target_label,
            )
        
        return triples


class OntologyWriterDisabled(BaseProcessor):
    """
    No-op ontology writer for when graph storage is disabled.
    
    Use this to skip graph writing entirely:
        pipeline = Pipeline(processors=[ConceptExtractor(), OntologyWriterDisabled()])
    """

    async def process(self, chunks: list[Chunk]) -> list[Chunk]:
        """Pass chunks through unchanged."""
        logger.debug("OntologyWriter disabled, skipping graph storage")
        return chunks

