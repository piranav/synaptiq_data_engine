"""
Service layer containing business logic.

Services are imported lazily to avoid loading optional dependencies
when they are not needed (e.g., background workers that do not use chat).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from synaptiq.services.auth_service import AuthService
    from synaptiq.services.chat_service import ChatService
    from synaptiq.services.notes_service import NotesService
    from synaptiq.services.search_service import SearchService
    from synaptiq.services.user_service import UserService

__all__ = ["AuthService", "ChatService", "NotesService", "SearchService", "UserService"]


def __getattr__(name: str):
    if name == "AuthService":
        from synaptiq.services.auth_service import AuthService

        return AuthService
    if name == "ChatService":
        from synaptiq.services.chat_service import ChatService

        return ChatService
    if name == "NotesService":
        from synaptiq.services.notes_service import NotesService

        return NotesService
    if name == "SearchService":
        from synaptiq.services.search_service import SearchService

        return SearchService
    if name == "UserService":
        from synaptiq.services.user_service import UserService

        return UserService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
