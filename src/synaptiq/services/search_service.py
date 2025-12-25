"""
Search service for unified cross-domain search.

Provides unified search across:
- Sources (Qdrant vector store)
- Notes (PostgreSQL full-text)
- Concepts (Fuseki graph store)
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Optional

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from synaptiq.domain.models import Note
from synaptiq.ontology.graph_manager import GraphManager
from synaptiq.processors.embedder import EmbeddingGenerator
from synaptiq.storage.fuseki import FusekiStore
from synaptiq.storage.qdrant import QdrantStore

logger = structlog.get_logger(__name__)


class SearchDomain(str, Enum):
    """Available search domains."""
    
    SOURCES = "sources"
    NOTES = "notes"
    CONCEPTS = "concepts"
    ALL = "all"


@dataclass
class UnifiedSearchResult:
    """A unified search result across domains."""
    
    id: str
    domain: str
    title: str
    content: str
    score: float
    url: Optional[str] = None
    source_type: Optional[str] = None
    concepts: list[str] = None
    metadata: dict = None
    created_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.concepts is None:
            self.concepts = []
        if self.metadata is None:
            self.metadata = {}


class SearchService:
    """
    Unified search service.
    
    Searches across multiple data stores and combines results.
    """
    
    def __init__(
        self,
        session: Optional[AsyncSession] = None,
        qdrant: Optional[QdrantStore] = None,
        fuseki: Optional[FusekiStore] = None,
        embedder: Optional[EmbeddingGenerator] = None,
    ):
        """
        Initialize search service.
        
        Args:
            session: SQLAlchemy async session (for notes)
            qdrant: Qdrant store (for sources)
            fuseki: Fuseki store (for concepts)
            embedder: Embedding generator
        """
        self.session = session
        self._qdrant = qdrant
        self._fuseki = fuseki
        self._embedder = embedder
        self._graph_manager: Optional[GraphManager] = None
    
    @property
    def qdrant(self) -> QdrantStore:
        """Lazy-initialize QdrantStore."""
        if self._qdrant is None:
            self._qdrant = QdrantStore()
        return self._qdrant
    
    @property
    def fuseki(self) -> FusekiStore:
        """Lazy-initialize FusekiStore."""
        if self._fuseki is None:
            self._fuseki = FusekiStore()
        return self._fuseki
    
    @property
    def embedder(self) -> EmbeddingGenerator:
        """Lazy-initialize EmbeddingGenerator."""
        if self._embedder is None:
            self._embedder = EmbeddingGenerator()
        return self._embedder
    
    @property
    def graph_manager(self) -> GraphManager:
        """Lazy-initialize GraphManager."""
        if self._graph_manager is None:
            self._graph_manager = GraphManager()
        return self._graph_manager
    
    async def search_sources(
        self,
        user_id: str,
        query: str,
        limit: int = 10,
        source_type: Optional[str] = None,
        has_definition: Optional[bool] = None,
        concepts: Optional[list[str]] = None,
        score_threshold: float = 0.5,
    ) -> list[UnifiedSearchResult]:
        """
        Search sources in vector store.
        
        Args:
            user_id: User ID
            query: Search query
            limit: Maximum results
            source_type: Optional filter by type
            has_definition: Optional filter for definitions
            concepts: Optional filter by concepts
            score_threshold: Minimum similarity score
            
        Returns:
            List of search results
        """
        try:
            # Generate query embedding
            query_vector = await self.embedder.generate_single(query)
            
            # Search Qdrant
            results = await self.qdrant.search(
                query_vector=query_vector,
                user_id=user_id,
                limit=limit,
                source_type=source_type,
                has_definition=has_definition,
                concepts=concepts,
                score_threshold=score_threshold,
            )
            
            # Transform to unified results
            unified_results = []
            for hit in results:
                payload = hit.get("payload", {})
                
                # Build citation URL
                url = payload.get("source_url", "")
                if payload.get("source_type") == "youtube" and payload.get("timestamp_start_ms"):
                    seconds = payload["timestamp_start_ms"] // 1000
                    url = f"{url}&t={seconds}s"
                
                unified_results.append(UnifiedSearchResult(
                    id=hit.get("id", ""),
                    domain=SearchDomain.SOURCES.value,
                    title=payload.get("source_title", ""),
                    content=payload.get("text", ""),
                    score=hit.get("score", 0),
                    url=url,
                    source_type=payload.get("source_type"),
                    concepts=payload.get("concepts", []),
                    metadata={
                        "timestamp_start_ms": payload.get("timestamp_start_ms"),
                        "timestamp_end_ms": payload.get("timestamp_end_ms"),
                        "has_definition": payload.get("has_definition", False),
                    },
                ))
            
            return unified_results
            
        except Exception as e:
            logger.error("Source search failed", user_id=user_id, error=str(e))
            return []
    
    async def search_notes(
        self,
        user_id: str,
        query: str,
        limit: int = 10,
    ) -> list[UnifiedSearchResult]:
        """
        Search notes in PostgreSQL.
        
        Args:
            user_id: User ID
            query: Search query
            limit: Maximum results
            
        Returns:
            List of search results
        """
        if not self.session:
            logger.warning("No session provided for notes search")
            return []
        
        try:
            # Simple ILIKE search
            search_pattern = f"%{query}%"
            
            result = await self.session.execute(
                select(Note)
                .where(
                    Note.user_id == user_id,
                    Note.is_archived == False,
                    (
                        Note.title.ilike(search_pattern) |
                        Note.plain_text.ilike(search_pattern)
                    ),
                )
                .order_by(Note.updated_at.desc())
                .limit(limit)
            )
            
            notes = list(result.scalars().all())
            
            # Transform to unified results
            # Simple relevance scoring based on position of match
            unified_results = []
            for note in notes:
                # Calculate simple relevance score
                title_lower = (note.title or "").lower()
                text_lower = (note.plain_text or "").lower()
                query_lower = query.lower()
                
                # Higher score if query in title
                if query_lower in title_lower:
                    score = 0.9
                elif query_lower in text_lower:
                    score = 0.7
                else:
                    score = 0.5
                
                unified_results.append(UnifiedSearchResult(
                    id=note.id,
                    domain=SearchDomain.NOTES.value,
                    title=note.title,
                    content=note.plain_text[:200] if note.plain_text else "",
                    score=score,
                    concepts=note.linked_concepts or [],
                    metadata={
                        "folder_id": note.folder_id,
                        "word_count": note.word_count,
                        "is_pinned": note.is_pinned,
                    },
                    created_at=note.created_at,
                ))
            
            return unified_results
            
        except Exception as e:
            logger.error("Notes search failed", user_id=user_id, error=str(e))
            return []
    
    async def search_concepts(
        self,
        user_id: str,
        query: str,
        limit: int = 10,
    ) -> list[UnifiedSearchResult]:
        """
        Search concepts in graph store.
        
        Args:
            user_id: User ID
            query: Search query
            limit: Maximum results
            
        Returns:
            List of search results
        """
        try:
            # Search for similar concepts
            concepts = await self.fuseki.find_similar_concepts(
                user_id=user_id,
                label=query,
                limit=limit,
            )
            
            # Transform to unified results
            unified_results = []
            for i, concept in enumerate(concepts):
                # Calculate simple relevance based on position
                # First results are typically more relevant
                score = 1.0 - (i * 0.05)  # Decreasing score
                
                unified_results.append(UnifiedSearchResult(
                    id=concept.get("uri", ""),
                    domain=SearchDomain.CONCEPTS.value,
                    title=concept.get("label", ""),
                    content=concept.get("definition", ""),
                    score=max(0.5, score),
                    metadata={
                        "source_title": concept.get("source_title"),
                        "source_url": concept.get("source_url"),
                    },
                ))
            
            return unified_results
            
        except Exception as e:
            logger.error("Concept search failed", user_id=user_id, error=str(e))
            return []
    
    async def unified_search(
        self,
        user_id: str,
        query: str,
        domains: Optional[list[SearchDomain]] = None,
        limit: int = 20,
        source_type: Optional[str] = None,
    ) -> list[UnifiedSearchResult]:
        """
        Search across multiple domains and merge results.
        
        Args:
            user_id: User ID
            query: Search query
            domains: Domains to search (default: all)
            limit: Maximum total results
            source_type: Optional filter for sources
            
        Returns:
            Combined and ranked search results
        """
        if not domains:
            domains = [SearchDomain.SOURCES, SearchDomain.NOTES, SearchDomain.CONCEPTS]
        
        all_results: list[UnifiedSearchResult] = []
        
        # Calculate per-domain limits
        per_domain_limit = max(5, limit // len(domains))
        
        # Search each domain
        if SearchDomain.SOURCES in domains or SearchDomain.ALL in domains:
            source_results = await self.search_sources(
                user_id=user_id,
                query=query,
                limit=per_domain_limit,
                source_type=source_type,
            )
            all_results.extend(source_results)
        
        if SearchDomain.NOTES in domains or SearchDomain.ALL in domains:
            note_results = await self.search_notes(
                user_id=user_id,
                query=query,
                limit=per_domain_limit,
            )
            all_results.extend(note_results)
        
        if SearchDomain.CONCEPTS in domains or SearchDomain.ALL in domains:
            concept_results = await self.search_concepts(
                user_id=user_id,
                query=query,
                limit=per_domain_limit,
            )
            all_results.extend(concept_results)
        
        # Sort by score and limit
        all_results.sort(key=lambda x: x.score, reverse=True)
        
        return all_results[:limit]
    
    async def search_definitions(
        self,
        user_id: str,
        query: str,
        limit: int = 5,
    ) -> list[UnifiedSearchResult]:
        """
        Search for definitions of a concept.
        
        Args:
            user_id: User ID
            query: Concept to find definition for
            limit: Maximum results
            
        Returns:
            Definition search results
        """
        # Search sources with definition filter
        return await self.search_sources(
            user_id=user_id,
            query=f"definition of {query}",
            limit=limit,
            has_definition=True,
            score_threshold=0.4,
        )
    
    async def search_by_concept(
        self,
        user_id: str,
        concept_uri: str,
        limit: int = 20,
    ) -> list[UnifiedSearchResult]:
        """
        Find all content related to a concept.
        
        Args:
            user_id: User ID
            concept_uri: URI of the concept
            limit: Maximum results
            
        Returns:
            Content related to the concept
        """
        all_results: list[UnifiedSearchResult] = []
        
        # Get concept label for text search
        concept_label = concept_uri.split("/")[-1].replace("_", " ")
        
        # Search sources mentioning the concept
        source_results = await self.search_sources(
            user_id=user_id,
            query=concept_label,
            limit=limit // 2,
            concepts=[concept_uri],
        )
        all_results.extend(source_results)
        
        # Search notes linked to the concept
        if self.session:
            result = await self.session.execute(
                select(Note)
                .where(
                    Note.user_id == user_id,
                    Note.linked_concepts.contains([concept_uri]),
                )
                .limit(limit // 2)
            )
            
            notes = list(result.scalars().all())
            for note in notes:
                all_results.append(UnifiedSearchResult(
                    id=note.id,
                    domain=SearchDomain.NOTES.value,
                    title=note.title,
                    content=note.plain_text[:200] if note.plain_text else "",
                    score=0.8,  # High relevance for linked notes
                    concepts=[concept_uri],
                ))
        
        return all_results[:limit]
    
    async def get_search_suggestions(
        self,
        user_id: str,
        query: str,
        limit: int = 5,
    ) -> list[str]:
        """
        Get search suggestions based on partial query.
        
        Args:
            user_id: User ID
            query: Partial query
            limit: Maximum suggestions
            
        Returns:
            List of suggested queries
        """
        suggestions = []
        
        # Get concept labels that match
        try:
            concepts = await self.fuseki.find_similar_concepts(
                user_id=user_id,
                label=query,
                limit=limit,
            )
            
            for concept in concepts:
                label = concept.get("label", "")
                if label and label.lower() != query.lower():
                    suggestions.append(label)
        except Exception as e:
            logger.warning("Failed to get concept suggestions", error=str(e))
        
        # Get note titles that match
        if self.session:
            try:
                result = await self.session.execute(
                    select(Note.title)
                    .where(
                        Note.user_id == user_id,
                        Note.title.ilike(f"%{query}%"),
                    )
                    .distinct()
                    .limit(limit)
                )
                
                for (title,) in result:
                    if title and title not in suggestions:
                        suggestions.append(title)
            except Exception as e:
                logger.warning("Failed to get note suggestions", error=str(e))
        
        return suggestions[:limit]
    
    async def close(self):
        """Close connections."""
        if self._qdrant:
            await self._qdrant.close()
        if self._fuseki:
            await self._fuseki.close()
        if self._graph_manager:
            await self._graph_manager.close()

