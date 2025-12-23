"""Storage layer for vectors, metadata, and graph data."""

from synaptiq.storage.qdrant import QdrantStore
from synaptiq.storage.mongodb import MongoDBStore

# FusekiStore is imported lazily to avoid circular imports with ontology package
# Use: from synaptiq.storage.fuseki import FusekiStore


def __getattr__(name: str):
    """Lazy import for FusekiStore to avoid circular imports."""
    if name == "FusekiStore":
        from synaptiq.storage.fuseki import FusekiStore
        return FusekiStore
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "QdrantStore",
    "MongoDBStore",
    "FusekiStore",
]


