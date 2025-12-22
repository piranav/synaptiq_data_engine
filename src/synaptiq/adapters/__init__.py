"""Source adapters for ingesting content from various sources."""

from synaptiq.adapters.base import BaseAdapter, AdapterFactory
from synaptiq.adapters.youtube import YouTubeAdapter
from synaptiq.adapters.web import WebAdapter
from synaptiq.adapters.notes import NotesAdapter

__all__ = [
    "BaseAdapter",
    "AdapterFactory",
    "YouTubeAdapter",
    "WebAdapter",
    "NotesAdapter",
]

