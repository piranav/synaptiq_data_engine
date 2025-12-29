"""
Knowledge extraction service for notes.

Handles:
- Multimodal knowledge extraction from notes
- Artifact storage and management
- Graph and vector store integration
"""

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from synaptiq.domain.artifacts import (
    CodeArtifact,
    ImageArtifact,
    NoteArtifact,
    TableArtifact,
)
from synaptiq.domain.models import Note
from synaptiq.processors.multimodal_pipeline import (
    MultimodalExtractionResult,
    MultimodalPipeline,
    ProcessedArtifact,
)
from synaptiq.storage.fuseki import FusekiStore
from synaptiq.storage.qdrant import QdrantStore

logger = structlog.get_logger(__name__)


class KnowledgeExtractionService:
    """
    Service for extracting and storing knowledge from notes.
    
    Orchestrates:
    - Multimodal content extraction
    - Artifact storage in PostgreSQL
    - Embedding storage in Qdrant
    - Graph updates in Fuseki
    """
    
    def __init__(
        self,
        session: AsyncSession,
        qdrant: Optional[QdrantStore] = None,
        fuseki: Optional[FusekiStore] = None,
        pipeline: Optional[MultimodalPipeline] = None,
    ):
        """
        Initialize the knowledge extraction service.
        
        Args:
            session: SQLAlchemy async session
            qdrant: Qdrant store (creates new if not provided)
            fuseki: Fuseki store (creates new if not provided)
            pipeline: Multimodal pipeline (creates new if not provided)
        """
        self.session = session
        self.qdrant = qdrant or QdrantStore()
        self.fuseki = fuseki or FusekiStore()
        self.pipeline = pipeline or MultimodalPipeline()
    
    async def extract_knowledge(
        self,
        note_id: str,
        user_id: str,
    ) -> dict:
        """
        Extract knowledge from a note and store in all backends.
        
        Args:
            note_id: Note ID to extract from
            user_id: User ID for isolation
            
        Returns:
            Extraction result summary
        """
        logger.info("Starting knowledge extraction", note_id=note_id, user_id=user_id)
        
        # 1. Get the note
        note = await self._get_note(note_id, user_id)
        if not note:
            raise ValueError(f"Note not found: {note_id}")
        
        # 2. Run multimodal extraction
        result = await self.pipeline.process_note(
            note_content=note.content or [],
            note_id=note_id,
            user_id=user_id,
            note_title=note.title or "Untitled",
        )
        
        # 3. Store artifacts in PostgreSQL
        await self._store_artifacts(result)
        
        # 4. Store embeddings in Qdrant
        await self._store_embeddings(result)
        
        # 5. Update knowledge graph in Fuseki
        await self._update_graph(result)
        
        # 6. Update note with extraction metadata
        await self._update_note_metadata(note_id, result)
        
        logger.info(
            "Knowledge extraction complete",
            note_id=note_id,
            text_chunks=len(result.text_chunks),
            artifacts=len(result.artifacts),
            concepts=len(result.all_concepts),
            time_ms=result.processing_time_ms,
        )
        
        return {
            "note_id": note_id,
            "text_chunks": len(result.text_chunks),
            "artifacts": len(result.artifacts),
            "concepts": result.all_concepts,
            "processing_time_ms": result.processing_time_ms,
            "breakdown": {
                "tables": result.table_count,
                "images": result.image_count,
                "code_blocks": result.code_count,
                "mermaid_diagrams": result.mermaid_count,
            },
        }
    
    async def _get_note(self, note_id: str, user_id: str) -> Optional[Note]:
        """Get a note by ID."""
        result = await self.session.execute(
            select(Note).where(
                Note.id == note_id,
                Note.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()
    
    async def _store_artifacts(self, result: MultimodalExtractionResult) -> None:
        """Store artifacts in PostgreSQL."""
        for artifact in result.artifacts:
            # Create base artifact
            note_artifact = NoteArtifact(
                id=artifact.id,
                note_id=result.note_id,
                user_id=result.user_id,
                artifact_type=artifact.type,
                position_in_source=artifact.position_in_source,
                context_before=artifact.context_before,
                context_after=artifact.context_after,
                raw_content=artifact.raw_content,
                description=artifact.description,
                combined_text_for_embedding=artifact.combined_text_for_embedding,
                processing_status="completed",
                processed_at=datetime.now(timezone.utc),
            )
            self.session.add(note_artifact)
            
            # Create type-specific artifact data
            if artifact.type == "table":
                await self._store_table_artifact(artifact)
            elif artifact.type == "image":
                await self._store_image_artifact(artifact)
            elif artifact.type in ("code", "mermaid"):
                await self._store_code_artifact(artifact)
        
        await self.session.flush()
        logger.debug("Artifacts stored", count=len(result.artifacts))
    
    async def _store_table_artifact(self, artifact: ProcessedArtifact) -> None:
        """Store table-specific data."""
        structured = artifact.extraction_data.get("structured", {})
        
        table_artifact = TableArtifact(
            artifact_id=artifact.id,
            raw_markdown=artifact.raw_content,
            structured_json=structured,
            row_facts=artifact.row_facts,
            row_count=structured.get("row_count", 0),
            column_count=structured.get("column_count", 0),
        )
        self.session.add(table_artifact)
    
    async def _store_image_artifact(self, artifact: ProcessedArtifact) -> None:
        """Store image-specific data."""
        data = artifact.extraction_data
        
        image_artifact = ImageArtifact(
            artifact_id=artifact.id,
            original_url=data.get("original_url"),
            image_type=data.get("image_type"),
            components=data.get("components", []),
            relationships=data.get("relationships", []),
            ocr_text=data.get("ocr_text"),
            data_points=data.get("data_points"),
        )
        self.session.add(image_artifact)
    
    async def _store_code_artifact(self, artifact: ProcessedArtifact) -> None:
        """Store code/mermaid-specific data."""
        data = artifact.extraction_data
        
        code_artifact = CodeArtifact(
            artifact_id=artifact.id,
            language=data.get("language", "unknown"),
            raw_code=artifact.raw_content,
            explanation=artifact.description,
            extracted_concepts=artifact.concepts,
            is_mermaid=1 if data.get("is_mermaid") else 0,
            mermaid_type=data.get("mermaid_type"),
            mermaid_components=data.get("mermaid_components", []),
            mermaid_relationships=data.get("mermaid_relationships", []),
        )
        self.session.add(code_artifact)
    
    async def _store_embeddings(self, result: MultimodalExtractionResult) -> None:
        """Store embeddings in Qdrant."""
        # Store text chunk embeddings
        if result.text_chunks:
            await self.qdrant.upsert_chunks(result.text_chunks)
        
        # Store artifact embeddings
        for artifact in result.artifacts:
            if artifact.embedding:
                await self._store_artifact_embedding(artifact, result.user_id)
            
            # Store row fact embeddings for tables
            if artifact.row_facts and artifact.row_fact_embeddings:
                await self._store_row_fact_embeddings(artifact, result.user_id)
        
        logger.debug(
            "Embeddings stored",
            text_chunks=len(result.text_chunks),
            artifacts=len(result.artifacts),
        )
    
    async def _store_artifact_embedding(
        self,
        artifact: ProcessedArtifact,
        user_id: str,
    ) -> None:
        """Store a single artifact embedding in Qdrant."""
        await self.qdrant.upsert_artifact(
            artifact_id=artifact.id,
            vector=artifact.embedding,
            user_id=user_id,
            artifact_type=artifact.type,
            source_note_id=artifact.note_id,
            description=artifact.description,
            text=artifact.combined_text_for_embedding,
            concepts=artifact.concepts,
        )
    
    async def _store_row_fact_embeddings(
        self,
        artifact: ProcessedArtifact,
        user_id: str,
    ) -> None:
        """Store row fact embeddings for tables."""
        await self.qdrant.upsert_table_row_facts(
            parent_artifact_id=artifact.id,
            facts=artifact.row_facts,
            embeddings=artifact.row_fact_embeddings,
            user_id=user_id,
            source_note_id=artifact.note_id,
        )
    
    async def _update_graph(self, result: MultimodalExtractionResult) -> None:
        """Update knowledge graph with artifact relationships."""
        try:
            # Ensure user graph exists
            if not await self.fuseki.user_graph_exists(result.user_id):
                await self.fuseki.create_user_graph(result.user_id)
            
            triples = []
            
            for artifact in result.artifacts:
                # Artifact node
                artifact_uri = f"pk:artifact_{artifact.id}"
                
                # Type triple
                type_uri = f"pk:{artifact.type.capitalize()}"
                triples.append({
                    "subject": artifact_uri,
                    "predicate": "rdf:type",
                    "object": type_uri,
                    "is_literal": False,
                })
                
                # Derived from note
                note_uri = f"pk:note_{result.note_id}"
                triples.append({
                    "subject": artifact_uri,
                    "predicate": "pk:derivedFrom",
                    "object": note_uri,
                    "is_literal": False,
                })
                
                # Description as label
                triples.append({
                    "subject": artifact_uri,
                    "predicate": "rdfs:label",
                    "object": artifact.description[:200],
                    "is_literal": True,
                })
                
                # Concept relationships
                for concept in artifact.concepts:
                    concept_uri = f"pk:{concept.replace(' ', '_')}"
                    triples.append({
                        "subject": artifact_uri,
                        "predicate": "pk:mentions",
                        "object": concept_uri,
                        "is_literal": False,
                    })
            
            if triples:
                await self.fuseki.insert_triples(result.user_id, triples)
            
            logger.debug("Graph updated", triples=len(triples))
            
        except Exception as e:
            logger.warning("Failed to update graph", error=str(e))
    
    async def _update_note_metadata(
        self,
        note_id: str,
        result: MultimodalExtractionResult,
    ) -> None:
        """Update note with extraction metadata."""
        await self.session.execute(
            update(Note)
            .where(Note.id == note_id)
            .values(
                linked_concepts=result.all_concepts,
                updated_at=datetime.now(timezone.utc),
            )
        )
    
    async def get_note_artifacts(
        self,
        note_id: str,
        user_id: str,
    ) -> list[dict]:
        """
        Get all artifacts for a note.
        
        Args:
            note_id: Note ID
            user_id: User ID
            
        Returns:
            List of artifact dicts
        """
        result = await self.session.execute(
            select(NoteArtifact)
            .where(
                NoteArtifact.note_id == note_id,
                NoteArtifact.user_id == user_id,
            )
            .order_by(NoteArtifact.position_in_source)
        )
        
        artifacts = result.scalars().all()
        
        return [
            {
                "id": a.id,
                "type": a.artifact_type,
                "position": a.position_in_source,
                "description": a.description,
                "status": a.processing_status,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in artifacts
        ]
    
    async def delete_note_artifacts(
        self,
        note_id: str,
        user_id: str,
    ) -> int:
        """
        Delete all artifacts for a note.
        
        Args:
            note_id: Note ID
            user_id: User ID
            
        Returns:
            Number of artifacts deleted
        """
        from sqlalchemy import delete
        
        # Get artifact IDs first (for Qdrant cleanup)
        result = await self.session.execute(
            select(NoteArtifact.id).where(
                NoteArtifact.note_id == note_id,
                NoteArtifact.user_id == user_id,
            )
        )
        artifact_ids = [str(r[0]) for r in result.all()]
        
        # Delete from PostgreSQL (cascades to type-specific tables)
        delete_result = await self.session.execute(
            delete(NoteArtifact).where(
                NoteArtifact.note_id == note_id,
                NoteArtifact.user_id == user_id,
            )
        )
        
        # Clean up Qdrant (artifact embeddings + row facts)
        for artifact_id in artifact_ids:
            try:
                from qdrant_client import models
                
                await self.qdrant.client.delete(
                    collection_name=self.qdrant.collection_name,
                    points_selector=models.FilterSelector(
                        filter=models.Filter(
                            should=[
                                models.FieldCondition(
                                    key="id",
                                    match=models.MatchValue(value=artifact_id),
                                ),
                                models.FieldCondition(
                                    key="parent_artifact_id",
                                    match=models.MatchValue(value=artifact_id),
                                ),
                            ]
                        )
                    ),
                )
            except Exception as e:
                logger.warning("Failed to delete from Qdrant", artifact_id=artifact_id, error=str(e))
        
        return delete_result.rowcount
