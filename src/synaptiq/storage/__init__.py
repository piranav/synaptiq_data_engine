"""Storage layer for vectors, metadata, and graph data."""

from synaptiq.storage.qdrant import QdrantStore
from synaptiq.storage.mongodb import MongoDBStore

# FusekiStore and S3Store are imported lazily to avoid requiring all dependencies
# Use: from synaptiq.storage.fuseki import FusekiStore
# Use: from synaptiq.storage.s3 import S3Store


def __getattr__(name: str):
    """Lazy import for optional storage backends."""
    if name == "FusekiStore":
        from synaptiq.storage.fuseki import FusekiStore
        return FusekiStore
    if name == "S3Store":
        from synaptiq.storage.s3 import S3Store
        return S3Store
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "QdrantStore",
    "MongoDBStore",
    "FusekiStore",
    "S3Store",
]


