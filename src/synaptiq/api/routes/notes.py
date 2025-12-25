"""
Notes API routes for managing user notes and folders.

Provides endpoints for:
- Notes CRUD operations
- Folder management
- Note search and filtering
- Concept extraction
"""

from typing import Any, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from synaptiq.api.middleware.auth import get_current_user
from synaptiq.domain.models import User
from synaptiq.infrastructure.database import get_async_session
from synaptiq.services.notes_service import NotesService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/notes", tags=["Notes"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================


class FolderCreate(BaseModel):
    """Request to create a folder."""
    
    name: str = Field(..., min_length=1, max_length=255, description="Folder name")
    parent_id: Optional[str] = Field(None, description="Parent folder ID")


class FolderUpdate(BaseModel):
    """Request to update a folder."""
    
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    parent_id: Optional[str] = Field(None, description="New parent ID (empty string for root)")


class FolderResponse(BaseModel):
    """Folder information."""
    
    id: str
    name: str
    parent_id: Optional[str]
    created_at: str
    updated_at: str


class FolderTreeItem(BaseModel):
    """Folder with nested children."""
    
    id: str
    name: str
    parent_id: Optional[str]
    children: list["FolderTreeItem"] = Field(default_factory=list)


FolderTreeItem.model_rebuild()


class NoteBlock(BaseModel):
    """Content block in a note."""
    
    type: str = Field(..., description="Block type: paragraph, heading, code, etc.")
    content: Any = Field(..., description="Block content")
    level: Optional[int] = Field(None, description="For headings: 1-6")
    language: Optional[str] = Field(None, description="For code blocks")


class NoteCreate(BaseModel):
    """Request to create a note."""
    
    title: str = Field(default="Untitled", max_length=500)
    content: list[dict] = Field(default_factory=list, description="Block-based content")
    folder_id: Optional[str] = Field(None, description="Folder to place note in")


class NoteUpdate(BaseModel):
    """Request to update a note."""
    
    title: Optional[str] = Field(None, max_length=500)
    content: Optional[list[dict]] = Field(None)
    folder_id: Optional[str] = Field(None, description="New folder ID (empty string to unfile)")
    is_pinned: Optional[bool] = None
    is_archived: Optional[bool] = None


class NoteResponse(BaseModel):
    """Note information."""
    
    id: str
    user_id: str
    folder_id: Optional[str]
    title: str
    content: list[dict]
    linked_concepts: list[str]
    word_count: int
    is_pinned: bool
    is_archived: bool
    last_extracted_at: Optional[str]
    created_at: str
    updated_at: str


class NoteSummary(BaseModel):
    """Note summary for listing."""
    
    id: str
    folder_id: Optional[str]
    title: str
    preview: Optional[str]
    word_count: int
    is_pinned: bool
    is_archived: bool
    updated_at: str


class NoteListResponse(BaseModel):
    """Response for note listing."""
    
    notes: list[NoteSummary]
    total: int


class NoteStatsResponse(BaseModel):
    """Note statistics."""
    
    total_notes: int
    active_notes: int
    archived_notes: int
    total_words: int
    folders: int


# =============================================================================
# DEPENDENCY INJECTION
# =============================================================================


async def get_notes_service(
    session: AsyncSession = Depends(get_async_session),
) -> NotesService:
    """Get NotesService instance."""
    return NotesService(session)


# =============================================================================
# FOLDER ENDPOINTS
# =============================================================================


@router.post(
    "/folders",
    response_model=FolderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create folder",
)
async def create_folder(
    body: FolderCreate,
    user: User = Depends(get_current_user),
    notes_service: NotesService = Depends(get_notes_service),
) -> FolderResponse:
    """
    Create a new folder.
    
    Optionally specify a parent_id to create a nested folder.
    """
    try:
        folder = await notes_service.create_folder(
            user_id=user.id,
            name=body.name,
            parent_id=body.parent_id,
        )
        
        return FolderResponse(
            id=folder.id,
            name=folder.name,
            parent_id=folder.parent_id,
            created_at=folder.created_at.isoformat(),
            updated_at=folder.updated_at.isoformat(),
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/folders",
    response_model=list[FolderResponse],
    summary="List folders",
)
async def list_folders(
    user: User = Depends(get_current_user),
    parent_id: Optional[str] = Query(None, description="Parent folder ID (omit for root)"),
    notes_service: NotesService = Depends(get_notes_service),
) -> list[FolderResponse]:
    """
    List folders at a specific level.
    
    Omit parent_id to get root-level folders.
    """
    folders = await notes_service.list_folders(
        user_id=user.id,
        parent_id=parent_id,
    )
    
    return [
        FolderResponse(
            id=f.id,
            name=f.name,
            parent_id=f.parent_id,
            created_at=f.created_at.isoformat(),
            updated_at=f.updated_at.isoformat(),
        )
        for f in folders
    ]


@router.get(
    "/folders/tree",
    response_model=list[FolderTreeItem],
    summary="Get folder tree",
)
async def get_folder_tree(
    user: User = Depends(get_current_user),
    notes_service: NotesService = Depends(get_notes_service),
) -> list[FolderTreeItem]:
    """
    Get complete folder hierarchy.
    
    Returns nested structure with children.
    """
    tree = await notes_service.get_folder_tree(user.id)
    return tree


@router.get(
    "/folders/{folder_id}",
    response_model=FolderResponse,
    summary="Get folder",
)
async def get_folder(
    folder_id: str,
    user: User = Depends(get_current_user),
    notes_service: NotesService = Depends(get_notes_service),
) -> FolderResponse:
    """Get a specific folder."""
    folder = await notes_service.get_folder(folder_id, user.id)
    
    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Folder not found: {folder_id}",
        )
    
    return FolderResponse(
        id=folder.id,
        name=folder.name,
        parent_id=folder.parent_id,
        created_at=folder.created_at.isoformat(),
        updated_at=folder.updated_at.isoformat(),
    )


@router.patch(
    "/folders/{folder_id}",
    response_model=FolderResponse,
    summary="Update folder",
)
async def update_folder(
    folder_id: str,
    body: FolderUpdate,
    user: User = Depends(get_current_user),
    notes_service: NotesService = Depends(get_notes_service),
) -> FolderResponse:
    """Update a folder (rename or move)."""
    try:
        folder = await notes_service.update_folder(
            folder_id=folder_id,
            user_id=user.id,
            name=body.name,
            parent_id=body.parent_id,
        )
        
        if not folder:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Folder not found: {folder_id}",
            )
        
        return FolderResponse(
            id=folder.id,
            name=folder.name,
            parent_id=folder.parent_id,
            created_at=folder.created_at.isoformat(),
            updated_at=folder.updated_at.isoformat(),
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.delete(
    "/folders/{folder_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete folder",
)
async def delete_folder(
    folder_id: str,
    user: User = Depends(get_current_user),
    cascade: bool = Query(False, description="Delete contents instead of moving to root"),
    notes_service: NotesService = Depends(get_notes_service),
) -> None:
    """
    Delete a folder.
    
    By default, contents are moved to root. Set cascade=true to delete contents.
    """
    deleted = await notes_service.delete_folder(
        folder_id=folder_id,
        user_id=user.id,
        cascade=cascade,
    )
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Folder not found: {folder_id}",
        )


# =============================================================================
# NOTE ENDPOINTS
# =============================================================================


@router.post(
    "",
    response_model=NoteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create note",
)
async def create_note(
    body: NoteCreate,
    user: User = Depends(get_current_user),
    notes_service: NotesService = Depends(get_notes_service),
) -> NoteResponse:
    """
    Create a new note.
    
    Content is block-based (similar to Notion):
    ```json
    {
      "content": [
        {"type": "paragraph", "content": "Hello world"},
        {"type": "heading", "level": 2, "content": "Section"},
        {"type": "code", "language": "python", "content": "print('hi')"}
      ]
    }
    ```
    """
    try:
        note = await notes_service.create_note(
            user_id=user.id,
            title=body.title,
            content=body.content,
            folder_id=body.folder_id,
        )
        
        return NoteResponse(
            id=note.id,
            user_id=note.user_id,
            folder_id=note.folder_id,
            title=note.title,
            content=note.content,
            linked_concepts=note.linked_concepts,
            word_count=note.word_count,
            is_pinned=note.is_pinned,
            is_archived=note.is_archived,
            last_extracted_at=note.last_extracted_at.isoformat() if note.last_extracted_at else None,
            created_at=note.created_at.isoformat(),
            updated_at=note.updated_at.isoformat(),
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "",
    response_model=NoteListResponse,
    summary="List notes",
)
async def list_notes(
    user: User = Depends(get_current_user),
    folder_id: Optional[str] = Query(None, description="Filter by folder (empty string for unfiled)"),
    include_archived: bool = Query(False),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    notes_service: NotesService = Depends(get_notes_service),
) -> NoteListResponse:
    """
    List notes with optional filtering.
    
    - Omit folder_id to get all notes
    - Set folder_id="" to get unfiled notes
    - Set folder_id to a UUID to get notes in that folder
    """
    notes = await notes_service.list_notes(
        user_id=user.id,
        folder_id=folder_id,
        include_archived=include_archived,
        limit=limit,
        offset=offset,
    )
    
    return NoteListResponse(
        notes=[
            NoteSummary(
                id=n.id,
                folder_id=n.folder_id,
                title=n.title,
                preview=n.plain_text[:100] if n.plain_text else None,
                word_count=n.word_count,
                is_pinned=n.is_pinned,
                is_archived=n.is_archived,
                updated_at=n.updated_at.isoformat(),
            )
            for n in notes
        ],
        total=len(notes),
    )


@router.get(
    "/recent",
    response_model=list[NoteSummary],
    summary="Get recent notes",
)
async def get_recent_notes(
    user: User = Depends(get_current_user),
    limit: int = Query(default=10, ge=1, le=50),
    notes_service: NotesService = Depends(get_notes_service),
) -> list[NoteSummary]:
    """Get recently updated notes."""
    notes = await notes_service.get_recent_notes(user.id, limit=limit)
    
    return [
        NoteSummary(
            id=n.id,
            folder_id=n.folder_id,
            title=n.title,
            preview=n.plain_text[:100] if n.plain_text else None,
            word_count=n.word_count,
            is_pinned=n.is_pinned,
            is_archived=n.is_archived,
            updated_at=n.updated_at.isoformat(),
        )
        for n in notes
    ]


@router.get(
    "/search",
    response_model=list[NoteSummary],
    summary="Search notes",
)
async def search_notes(
    user: User = Depends(get_current_user),
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(default=50, ge=1, le=100),
    notes_service: NotesService = Depends(get_notes_service),
) -> list[NoteSummary]:
    """Search notes by title and content."""
    notes = await notes_service.search_notes(
        user_id=user.id,
        query=q,
        limit=limit,
    )
    
    return [
        NoteSummary(
            id=n.id,
            folder_id=n.folder_id,
            title=n.title,
            preview=n.plain_text[:100] if n.plain_text else None,
            word_count=n.word_count,
            is_pinned=n.is_pinned,
            is_archived=n.is_archived,
            updated_at=n.updated_at.isoformat(),
        )
        for n in notes
    ]


@router.get(
    "/stats",
    response_model=NoteStatsResponse,
    summary="Get note statistics",
)
async def get_note_stats(
    user: User = Depends(get_current_user),
    notes_service: NotesService = Depends(get_notes_service),
) -> NoteStatsResponse:
    """Get statistics about user's notes."""
    stats = await notes_service.get_note_stats(user.id)
    return NoteStatsResponse(**stats)


@router.get(
    "/{note_id}",
    response_model=NoteResponse,
    summary="Get note",
)
async def get_note(
    note_id: str,
    user: User = Depends(get_current_user),
    notes_service: NotesService = Depends(get_notes_service),
) -> NoteResponse:
    """Get a specific note with full content."""
    note = await notes_service.get_note(note_id, user.id)
    
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Note not found: {note_id}",
        )
    
    return NoteResponse(
        id=note.id,
        user_id=note.user_id,
        folder_id=note.folder_id,
        title=note.title,
        content=note.content,
        linked_concepts=note.linked_concepts,
        word_count=note.word_count,
        is_pinned=note.is_pinned,
        is_archived=note.is_archived,
        last_extracted_at=note.last_extracted_at.isoformat() if note.last_extracted_at else None,
        created_at=note.created_at.isoformat(),
        updated_at=note.updated_at.isoformat(),
    )


@router.patch(
    "/{note_id}",
    response_model=NoteResponse,
    summary="Update note",
)
async def update_note(
    note_id: str,
    body: NoteUpdate,
    user: User = Depends(get_current_user),
    notes_service: NotesService = Depends(get_notes_service),
) -> NoteResponse:
    """
    Update a note.
    
    All fields are optional - only provided fields are updated.
    Good for auto-save functionality.
    """
    try:
        note = await notes_service.update_note(
            note_id=note_id,
            user_id=user.id,
            title=body.title,
            content=body.content,
            folder_id=body.folder_id,
            is_pinned=body.is_pinned,
            is_archived=body.is_archived,
        )
        
        if not note:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Note not found: {note_id}",
            )
        
        return NoteResponse(
            id=note.id,
            user_id=note.user_id,
            folder_id=note.folder_id,
            title=note.title,
            content=note.content,
            linked_concepts=note.linked_concepts,
            word_count=note.word_count,
            is_pinned=note.is_pinned,
            is_archived=note.is_archived,
            last_extracted_at=note.last_extracted_at.isoformat() if note.last_extracted_at else None,
            created_at=note.created_at.isoformat(),
            updated_at=note.updated_at.isoformat(),
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.delete(
    "/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete note",
)
async def delete_note(
    note_id: str,
    user: User = Depends(get_current_user),
    notes_service: NotesService = Depends(get_notes_service),
) -> None:
    """Delete a note permanently."""
    deleted = await notes_service.delete_note(note_id, user.id)
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Note not found: {note_id}",
        )


# =============================================================================
# CONCEPT EXTRACTION
# =============================================================================


@router.post(
    "/{note_id}/extract",
    response_model=list[str],
    summary="Extract concepts from note",
)
async def extract_concepts(
    note_id: str,
    user: User = Depends(get_current_user),
    notes_service: NotesService = Depends(get_notes_service),
) -> list[str]:
    """
    Extract and link concepts from note content.
    
    Finds [[concept]] links and optionally uses AI to identify
    additional concepts.
    """
    try:
        concepts = await notes_service.extract_concepts(note_id, user.id)
        return concepts
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get(
    "/{note_id}/concepts",
    response_model=list[str],
    summary="Get linked concepts",
)
async def get_linked_concepts(
    note_id: str,
    user: User = Depends(get_current_user),
    notes_service: NotesService = Depends(get_notes_service),
) -> list[str]:
    """Get concepts linked to this note."""
    note = await notes_service.get_note(note_id, user.id)
    
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Note not found: {note_id}",
        )
    
    return note.linked_concepts or []

