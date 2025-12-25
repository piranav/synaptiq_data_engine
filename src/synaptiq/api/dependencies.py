"""
FastAPI dependency injection for shared resources.
"""

from typing import AsyncGenerator

from synaptiq.processors.embedder import EmbeddingGenerator
from synaptiq.storage.mongodb import MongoDBStore
from synaptiq.storage.qdrant import QdrantStore


# Singleton instances
_qdrant_store: QdrantStore | None = None
_mongodb_store: MongoDBStore | None = None
_embedder: EmbeddingGenerator | None = None


async def get_qdrant() -> AsyncGenerator[QdrantStore, None]:
    """
    Dependency for Qdrant store.
    Uses a singleton pattern for connection reuse.
    """
    global _qdrant_store
    if _qdrant_store is None:
        _qdrant_store = QdrantStore()
        await _qdrant_store.ensure_collection()
    yield _qdrant_store


async def get_mongodb() -> AsyncGenerator[MongoDBStore, None]:
    """
    Dependency for MongoDB store.
    Uses a singleton pattern for connection reuse.
    """
    global _mongodb_store
    if _mongodb_store is None:
        _mongodb_store = MongoDBStore()
        await _mongodb_store.ensure_indexes()
    yield _mongodb_store


async def get_embedder() -> AsyncGenerator[EmbeddingGenerator, None]:
    """
    Dependency for embedding generator.
    Uses a singleton pattern for client reuse.
    """
    global _embedder
    if _embedder is None:
        _embedder = EmbeddingGenerator()
    yield _embedder



# ... imports

from synaptiq.ontology.graph_manager import GraphManager

# ... singletons
_graph_manager: GraphManager | None = None


# ... functions

async def get_graph_manager() -> AsyncGenerator[GraphManager, None]:
    """
    Dependency for graph manager.
    Uses a singleton pattern.
    """
    global _graph_manager
    if _graph_manager is None:
        _graph_manager = GraphManager()
        # await _graph_manager.initialize() # Check if init is needed
    yield _graph_manager

async def cleanup_resources() -> None:
    """Cleanup all singleton resources on shutdown."""
    global _qdrant_store, _mongodb_store, _graph_manager

    if _qdrant_store is not None:
        await _qdrant_store.close()
        _qdrant_store = None

    if _mongodb_store is not None:
        await _mongodb_store.close()
        _mongodb_store = None
        
    if _graph_manager is not None:
        await _graph_manager.close()
        _graph_manager = None



