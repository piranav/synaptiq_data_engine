"""
User service for managing user lifecycle and knowledge space provisioning.

Handles:
- Knowledge graph provisioning (Fuseki named graph)
- User statistics aggregation
- User data export (GDPR)
- User deletion with cascade
"""

from typing import Any, Optional

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from synaptiq.domain.models import User, UserSettings
from synaptiq.ontology.graph_manager import GraphManager
from synaptiq.storage.fuseki import FusekiStore
from synaptiq.storage.qdrant import QdrantStore

logger = structlog.get_logger(__name__)


class UserStats:
    """Statistics for a user's knowledge base."""
    
    def __init__(
        self,
        concepts_count: int = 0,
        sources_count: int = 0,
        chunks_count: int = 0,
        definitions_count: int = 0,
        relationships_count: int = 0,
        graph_uri: Optional[str] = None,
    ):
        self.concepts_count = concepts_count
        self.sources_count = sources_count
        self.chunks_count = chunks_count
        self.definitions_count = definitions_count
        self.relationships_count = relationships_count
        self.graph_uri = graph_uri
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "concepts_count": self.concepts_count,
            "sources_count": self.sources_count,
            "chunks_count": self.chunks_count,
            "definitions_count": self.definitions_count,
            "relationships_count": self.relationships_count,
            "graph_uri": self.graph_uri,
        }


class UserService:
    """
    Service for user lifecycle management.
    
    Coordinates between:
    - PostgreSQL (user records)
    - Fuseki (knowledge graphs)
    - Qdrant (vector embeddings)
    """
    
    def __init__(self, session: AsyncSession):
        """
        Initialize user service.
        
        Args:
            session: SQLAlchemy async session
        """
        self.session = session
        self._graph_manager: Optional[GraphManager] = None
        self._qdrant: Optional[QdrantStore] = None
    
    @property
    def graph_manager(self) -> GraphManager:
        """Lazy-initialize GraphManager."""
        if self._graph_manager is None:
            self._graph_manager = GraphManager()
        return self._graph_manager
    
    @property
    def qdrant(self) -> QdrantStore:
        """Lazy-initialize QdrantStore."""
        if self._qdrant is None:
            self._qdrant = QdrantStore()
        return self._qdrant
    
    async def get_user(self, user_id: str) -> Optional[User]:
        """
        Get a user by ID.
        
        Args:
            user_id: User ID
            
        Returns:
            User if found, None otherwise
        """
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def get_user_settings(self, user_id: str) -> Optional[UserSettings]:
        """
        Get user settings.
        
        Args:
            user_id: User ID
            
        Returns:
            UserSettings if found, None otherwise
        """
        result = await self.session.execute(
            select(UserSettings).where(UserSettings.user_id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def update_user(self, user_id: str, **updates) -> Optional[User]:
        """
        Update user fields.
        
        Args:
            user_id: User ID
            **updates: Fields to update
            
        Returns:
            Updated User or None if not found
        """
        # Filter out None values
        updates = {k: v for k, v in updates.items() if v is not None}
        
        if not updates:
            return await self.get_user(user_id)
        
        await self.session.execute(
            update(User).where(User.id == user_id).values(**updates)
        )
        
        return await self.get_user(user_id)
    
    async def update_settings(self, user_id: str, **updates) -> Optional[UserSettings]:
        """
        Update user settings.
        
        Args:
            user_id: User ID
            **updates: Settings to update
            
        Returns:
            Updated UserSettings or None if not found
        """
        # Filter out None values
        updates = {k: v for k, v in updates.items() if v is not None}
        
        if not updates:
            return await self.get_user_settings(user_id)
        
        # Check if settings exist
        settings = await self.get_user_settings(user_id)
        if not settings:
            # Create default settings with updates
            settings = UserSettings(user_id=user_id, **updates)
            self.session.add(settings)
        else:
            await self.session.execute(
                update(UserSettings)
                .where(UserSettings.user_id == user_id)
                .values(**updates)
            )
        
        return await self.get_user_settings(user_id)
    
    async def provision_knowledge_space(self, user_id: str) -> str:
        """
        Provision a knowledge graph for a new user.
        
        Creates a named graph in Fuseki and updates the user record
        with the graph URI.
        
        Args:
            user_id: User ID
            
        Returns:
            Graph URI
        """
        try:
            logger.info("Provisioning knowledge space", user_id=user_id)
            
            # Create named graph
            graph_uri = await self.graph_manager.onboard_user(user_id)
            
            # Update user record with graph URI
            await self.session.execute(
                update(User).where(User.id == user_id).values(graph_uri=graph_uri)
            )
            
            logger.info(
                "Knowledge space provisioned",
                user_id=user_id,
                graph_uri=graph_uri,
            )
            
            return graph_uri
            
        except Exception as e:
            logger.error(
                "Failed to provision knowledge space",
                user_id=user_id,
                error=str(e),
            )
            raise
    
    async def get_user_stats(self, user_id: str) -> UserStats:
        """
        Get statistics for a user's knowledge base.
        
        Aggregates data from:
        - Fuseki (concepts, relationships)
        - Qdrant (chunks)
        
        Args:
            user_id: User ID
            
        Returns:
            UserStats with counts
        """
        stats = UserStats()
        
        try:
            # Get graph stats from Fuseki
            graph_stats = await self.graph_manager.get_graph_statistics(user_id)
            stats.concepts_count = graph_stats.get("concept_count", 0)
            stats.sources_count = graph_stats.get("source_count", 0)
            stats.definitions_count = graph_stats.get("definition_count", 0)
            stats.relationships_count = graph_stats.get("relationship_count", 0)
            stats.graph_uri = graph_stats.get("graph_uri")
            
        except Exception as e:
            logger.warning("Failed to get graph stats", user_id=user_id, error=str(e))
        
        try:
            # Get chunk count from Qdrant
            # This requires a count query filtered by user_id
            # For now, we'll use an estimate or skip
            # In production, implement a proper count method in QdrantStore
            pass
            
        except Exception as e:
            logger.warning("Failed to get vector stats", user_id=user_id, error=str(e))
        
        return stats
    
    async def export_user_data(self, user_id: str) -> dict[str, Any]:
        """
        Export all user data (GDPR compliance).
        
        Returns:
        - User profile
        - Settings
        - Knowledge graph (Turtle format)
        - Vector store metadata (not embeddings)
        
        Args:
            user_id: User ID
            
        Returns:
            Dictionary with all user data
        """
        export_data = {}
        
        # Export user profile
        user = await self.get_user(user_id)
        if user:
            export_data["profile"] = {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "created_at": user.created_at.isoformat() if user.created_at else None,
            }
        
        # Export settings
        settings = await self.get_user_settings(user_id)
        if settings:
            export_data["settings"] = {
                "theme": settings.theme,
                "accent_color": settings.accent_color,
                "sidebar_collapsed": settings.sidebar_collapsed,
                "density": settings.density,
                "processing_mode": settings.processing_mode,
                "analytics_opt_in": settings.analytics_opt_in,
            }
        
        # Export knowledge graph
        try:
            graph_data = await self.graph_manager.export_graph(user_id, format="turtle")
            export_data["knowledge_graph"] = {
                "format": "turtle",
                "data": graph_data,
            }
        except Exception as e:
            logger.warning("Failed to export graph", user_id=user_id, error=str(e))
            export_data["knowledge_graph"] = {"error": str(e)}
        
        # Export stats
        stats = await self.get_user_stats(user_id)
        export_data["stats"] = stats.to_dict()
        
        return export_data
    
    async def delete_user(self, user_id: str) -> dict[str, Any]:
        """
        Delete all user data (GDPR right to erasure).
        
        Cascades to:
        - PostgreSQL (user, settings, sessions)
        - Fuseki (named graph)
        - Qdrant (vectors)
        
        Args:
            user_id: User ID
            
        Returns:
            Dictionary with deletion counts
        """
        result = {
            "user_id": user_id,
            "deleted": {},
        }
        
        try:
            # Delete from Fuseki
            await self.graph_manager.delete_user_data(user_id)
            result["deleted"]["graph"] = True
            logger.info("Deleted user graph", user_id=user_id)
        except Exception as e:
            logger.error("Failed to delete user graph", user_id=user_id, error=str(e))
            result["deleted"]["graph"] = False
        
        try:
            # Delete from Qdrant
            qdrant_count = await self.qdrant.delete_by_user(user_id)
            result["deleted"]["vectors"] = qdrant_count
            logger.info("Deleted user vectors", user_id=user_id, count=qdrant_count)
        except Exception as e:
            logger.error("Failed to delete user vectors", user_id=user_id, error=str(e))
            result["deleted"]["vectors"] = 0
        
        try:
            # Delete from PostgreSQL (cascades to settings, sessions)
            user = await self.get_user(user_id)
            if user:
                await self.session.delete(user)
                result["deleted"]["user"] = True
                logger.info("Deleted user record", user_id=user_id)
            else:
                result["deleted"]["user"] = False
        except Exception as e:
            logger.error("Failed to delete user record", user_id=user_id, error=str(e))
            result["deleted"]["user"] = False
        
        return result
    
    async def close(self):
        """Close connections."""
        if self._graph_manager:
            await self._graph_manager.close()
        if self._qdrant:
            await self._qdrant.close()

