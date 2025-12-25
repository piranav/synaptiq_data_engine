"""
Notes service for managing user notes and folders.

Handles:
- Notes CRUD operations
- Folder management
- Concept linking and extraction
- Search and filtering
"""

import re
from datetime import datetime, timezone
from typing import Any, Optional

import structlog
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from synaptiq.domain.models import Folder, Note

logger = structlog.get_logger(__name__)


class NotesService:
    """
    Service for notes and folder operations.
    
    Provides:
    - Notes CRUD with block-based content
    - Folder hierarchy management
    - Concept extraction and linking
    - Full-text search
    """
    
    def __init__(self, session: AsyncSession):
        """
        Initialize notes service.
        
        Args:
            session: SQLAlchemy async session
        """
        self.session = session
    
    # =========================================================================
    # FOLDER OPERATIONS
    # =========================================================================
    
    async def create_folder(
        self,
        user_id: str,
        name: str,
        parent_id: Optional[str] = None,
    ) -> Folder:
        """
        Create a new folder.
        
        Args:
            user_id: User ID
            name: Folder name
            parent_id: Optional parent folder ID
            
        Returns:
            Created Folder
        """
        # Verify parent exists if provided
        if parent_id:
            parent = await self.get_folder(parent_id, user_id)
            if not parent:
                raise ValueError(f"Parent folder not found: {parent_id}")
        
        folder = Folder(
            user_id=user_id,
            name=name,
            parent_id=parent_id,
        )
        self.session.add(folder)
        await self.session.flush()
        await self.session.refresh(folder)
        
        logger.info(
            "Folder created",
            folder_id=folder.id,
            user_id=user_id,
            name=name,
        )
        
        return folder
    
    async def get_folder(
        self,
        folder_id: str,
        user_id: str,
    ) -> Optional[Folder]:
        """
        Get a folder by ID.
        
        Args:
            folder_id: Folder ID
            user_id: User ID (for ownership verification)
            
        Returns:
            Folder if found, None otherwise
        """
        result = await self.session.execute(
            select(Folder).where(
                Folder.id == folder_id,
                Folder.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()
    
    async def list_folders(
        self,
        user_id: str,
        parent_id: Optional[str] = None,
    ) -> list[Folder]:
        """
        List folders for a user.
        
        Args:
            user_id: User ID
            parent_id: Optional parent folder ID (None for root folders)
            
        Returns:
            List of Folders
        """
        query = select(Folder).where(Folder.user_id == user_id)
        
        if parent_id:
            query = query.where(Folder.parent_id == parent_id)
        else:
            query = query.where(Folder.parent_id.is_(None))
        
        query = query.order_by(Folder.name)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def get_folder_tree(
        self,
        user_id: str,
    ) -> list[dict]:
        """
        Get complete folder tree for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            List of folder dicts with nested children
        """
        # Get all folders
        result = await self.session.execute(
            select(Folder)
            .where(Folder.user_id == user_id)
            .order_by(Folder.name)
        )
        folders = list(result.scalars().all())
        
        # Build tree structure
        folder_dict = {
            f.id: {
                "id": f.id,
                "name": f.name,
                "parent_id": f.parent_id,
                "children": [],
            }
            for f in folders
        }
        
        roots = []
        for f in folders:
            if f.parent_id and f.parent_id in folder_dict:
                folder_dict[f.parent_id]["children"].append(folder_dict[f.id])
            else:
                roots.append(folder_dict[f.id])
        
        return roots
    
    async def update_folder(
        self,
        folder_id: str,
        user_id: str,
        name: Optional[str] = None,
        parent_id: Optional[str] = None,
    ) -> Optional[Folder]:
        """
        Update a folder.
        
        Args:
            folder_id: Folder ID
            user_id: User ID
            name: New name
            parent_id: New parent ID (use empty string to move to root)
            
        Returns:
            Updated Folder or None if not found
        """
        updates = {"updated_at": datetime.now(timezone.utc)}
        
        if name is not None:
            updates["name"] = name
        
        if parent_id is not None:
            if parent_id == "":
                updates["parent_id"] = None
            else:
                # Verify parent exists
                parent = await self.get_folder(parent_id, user_id)
                if not parent:
                    raise ValueError(f"Parent folder not found: {parent_id}")
                # Prevent circular references
                if parent_id == folder_id:
                    raise ValueError("Folder cannot be its own parent")
                updates["parent_id"] = parent_id
        
        await self.session.execute(
            update(Folder)
            .where(
                Folder.id == folder_id,
                Folder.user_id == user_id,
            )
            .values(**updates)
        )
        
        return await self.get_folder(folder_id, user_id)
    
    async def delete_folder(
        self,
        folder_id: str,
        user_id: str,
        cascade: bool = False,
    ) -> bool:
        """
        Delete a folder.
        
        Args:
            folder_id: Folder ID
            user_id: User ID
            cascade: If True, delete all contents; if False, move contents to root
            
        Returns:
            True if deleted
        """
        folder = await self.get_folder(folder_id, user_id)
        if not folder:
            return False
        
        if not cascade:
            # Move child folders to root
            await self.session.execute(
                update(Folder)
                .where(
                    Folder.parent_id == folder_id,
                    Folder.user_id == user_id,
                )
                .values(parent_id=None)
            )
            
            # Move notes to root
            await self.session.execute(
                update(Note)
                .where(
                    Note.folder_id == folder_id,
                    Note.user_id == user_id,
                )
                .values(folder_id=None)
            )
        
        # Delete folder (cascade handles the rest if enabled)
        await self.session.execute(
            delete(Folder).where(
                Folder.id == folder_id,
                Folder.user_id == user_id,
            )
        )
        
        logger.info("Folder deleted", folder_id=folder_id, user_id=user_id)
        return True
    
    # =========================================================================
    # NOTE OPERATIONS
    # =========================================================================
    
    async def create_note(
        self,
        user_id: str,
        title: str = "Untitled",
        content: Optional[list[dict]] = None,
        folder_id: Optional[str] = None,
    ) -> Note:
        """
        Create a new note.
        
        Args:
            user_id: User ID
            title: Note title
            content: Block-based content (list of block dicts)
            folder_id: Optional folder ID
            
        Returns:
            Created Note
        """
        content = content or []
        
        # Verify folder exists if provided
        if folder_id:
            folder = await self.get_folder(folder_id, user_id)
            if not folder:
                raise ValueError(f"Folder not found: {folder_id}")
        
        # Extract plain text for search
        plain_text = self._extract_plain_text(content)
        word_count = len(plain_text.split()) if plain_text else 0
        
        # Extract concept links from content
        linked_concepts = self._extract_concept_links(content)
        
        note = Note(
            user_id=user_id,
            title=title,
            content=content,
            plain_text=plain_text,
            folder_id=folder_id,
            linked_concepts=linked_concepts,
            word_count=word_count,
        )
        self.session.add(note)
        await self.session.flush()
        await self.session.refresh(note)
        
        logger.info(
            "Note created",
            note_id=note.id,
            user_id=user_id,
            title=title,
        )
        
        return note
    
    async def get_note(
        self,
        note_id: str,
        user_id: str,
    ) -> Optional[Note]:
        """
        Get a note by ID.
        
        Args:
            note_id: Note ID
            user_id: User ID (for ownership verification)
            
        Returns:
            Note if found, None otherwise
        """
        result = await self.session.execute(
            select(Note).where(
                Note.id == note_id,
                Note.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()
    
    async def list_notes(
        self,
        user_id: str,
        folder_id: Optional[str] = None,
        include_archived: bool = False,
        pinned_first: bool = True,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Note]:
        """
        List notes for a user.
        
        Args:
            user_id: User ID
            folder_id: Optional folder filter (None for all, "" for unfiled)
            include_archived: Include archived notes
            pinned_first: Sort pinned notes first
            limit: Maximum results
            offset: Pagination offset
            
        Returns:
            List of Notes
        """
        query = select(Note).where(Note.user_id == user_id)
        
        # Folder filter
        if folder_id == "":
            query = query.where(Note.folder_id.is_(None))
        elif folder_id:
            query = query.where(Note.folder_id == folder_id)
        
        # Archive filter
        if not include_archived:
            query = query.where(Note.is_archived == False)
        
        # Ordering
        if pinned_first:
            query = query.order_by(
                Note.is_pinned.desc(),
                Note.updated_at.desc(),
            )
        else:
            query = query.order_by(Note.updated_at.desc())
        
        query = query.limit(limit).offset(offset)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def update_note(
        self,
        note_id: str,
        user_id: str,
        title: Optional[str] = None,
        content: Optional[list[dict]] = None,
        folder_id: Optional[str] = None,
        is_pinned: Optional[bool] = None,
        is_archived: Optional[bool] = None,
    ) -> Optional[Note]:
        """
        Update a note.
        
        Args:
            note_id: Note ID
            user_id: User ID
            title: New title
            content: New content
            folder_id: New folder ID (use "" to unfile)
            is_pinned: Pin status
            is_archived: Archive status
            
        Returns:
            Updated Note or None if not found
        """
        updates: dict[str, Any] = {"updated_at": datetime.now(timezone.utc)}
        
        if title is not None:
            updates["title"] = title
        
        if content is not None:
            updates["content"] = content
            updates["plain_text"] = self._extract_plain_text(content)
            updates["word_count"] = len(updates["plain_text"].split()) if updates["plain_text"] else 0
            updates["linked_concepts"] = self._extract_concept_links(content)
        
        if folder_id is not None:
            if folder_id == "":
                updates["folder_id"] = None
            else:
                folder = await self.get_folder(folder_id, user_id)
                if not folder:
                    raise ValueError(f"Folder not found: {folder_id}")
                updates["folder_id"] = folder_id
        
        if is_pinned is not None:
            updates["is_pinned"] = is_pinned
        
        if is_archived is not None:
            updates["is_archived"] = is_archived
        
        await self.session.execute(
            update(Note)
            .where(
                Note.id == note_id,
                Note.user_id == user_id,
            )
            .values(**updates)
        )
        
        return await self.get_note(note_id, user_id)
    
    async def delete_note(
        self,
        note_id: str,
        user_id: str,
    ) -> bool:
        """
        Delete a note.
        
        Args:
            note_id: Note ID
            user_id: User ID
            
        Returns:
            True if deleted
        """
        result = await self.session.execute(
            delete(Note).where(
                Note.id == note_id,
                Note.user_id == user_id,
            )
        )
        
        deleted = result.rowcount > 0
        if deleted:
            logger.info("Note deleted", note_id=note_id, user_id=user_id)
        
        return deleted
    
    # =========================================================================
    # SEARCH AND FILTER
    # =========================================================================
    
    async def search_notes(
        self,
        user_id: str,
        query: str,
        limit: int = 50,
    ) -> list[Note]:
        """
        Search notes by title and content.
        
        Args:
            user_id: User ID
            query: Search query
            limit: Maximum results
            
        Returns:
            List of matching Notes
        """
        # Simple ILIKE search - for production, use full-text search
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
        
        return list(result.scalars().all())
    
    async def get_recent_notes(
        self,
        user_id: str,
        limit: int = 10,
    ) -> list[Note]:
        """
        Get recently updated notes.
        
        Args:
            user_id: User ID
            limit: Maximum results
            
        Returns:
            List of recent Notes
        """
        result = await self.session.execute(
            select(Note)
            .where(
                Note.user_id == user_id,
                Note.is_archived == False,
            )
            .order_by(Note.updated_at.desc())
            .limit(limit)
        )
        
        return list(result.scalars().all())
    
    async def get_notes_by_concept(
        self,
        user_id: str,
        concept_uri: str,
        limit: int = 50,
    ) -> list[Note]:
        """
        Get notes linked to a specific concept.
        
        Args:
            user_id: User ID
            concept_uri: Concept URI to search for
            limit: Maximum results
            
        Returns:
            List of linked Notes
        """
        # Search in linked_concepts JSONB array
        result = await self.session.execute(
            select(Note)
            .where(
                Note.user_id == user_id,
                Note.linked_concepts.contains([concept_uri]),
            )
            .order_by(Note.updated_at.desc())
            .limit(limit)
        )
        
        return list(result.scalars().all())
    
    # =========================================================================
    # CONCEPT EXTRACTION
    # =========================================================================
    
    async def extract_concepts(
        self,
        note_id: str,
        user_id: str,
    ) -> list[str]:
        """
        Extract and link concepts from note content.
        
        Uses LLM to identify concepts not yet linked via [[ ]] syntax.
        
        Args:
            note_id: Note ID
            user_id: User ID
            
        Returns:
            List of extracted concept labels
        """
        note = await self.get_note(note_id, user_id)
        if not note:
            raise ValueError(f"Note not found: {note_id}")
        
        # For now, just extract [[ ]] links
        # In production, integrate with concept extractor
        manual_links = self._extract_concept_links(note.content)
        
        # Update note with extraction timestamp
        await self.session.execute(
            update(Note)
            .where(Note.id == note_id)
            .values(
                linked_concepts=manual_links,
                last_extracted_at=datetime.now(timezone.utc),
            )
        )
        
        return manual_links
    
    # =========================================================================
    # STATISTICS
    # =========================================================================
    
    async def get_note_stats(
        self,
        user_id: str,
    ) -> dict:
        """
        Get statistics about user's notes.
        
        Args:
            user_id: User ID
            
        Returns:
            Dict with note statistics
        """
        # Total notes
        total_result = await self.session.execute(
            select(func.count(Note.id)).where(Note.user_id == user_id)
        )
        total = total_result.scalar() or 0
        
        # Archived notes
        archived_result = await self.session.execute(
            select(func.count(Note.id)).where(
                Note.user_id == user_id,
                Note.is_archived == True,
            )
        )
        archived = archived_result.scalar() or 0
        
        # Total word count
        words_result = await self.session.execute(
            select(func.sum(Note.word_count)).where(Note.user_id == user_id)
        )
        total_words = words_result.scalar() or 0
        
        # Folder count
        folders_result = await self.session.execute(
            select(func.count(Folder.id)).where(Folder.user_id == user_id)
        )
        folders = folders_result.scalar() or 0
        
        return {
            "total_notes": total,
            "active_notes": total - archived,
            "archived_notes": archived,
            "total_words": total_words,
            "folders": folders,
        }
    
    # =========================================================================
    # HELPER METHODS
    # =========================================================================
    
    def _extract_plain_text(self, content: list[dict]) -> str:
        """
        Extract plain text from block-based content.
        
        Args:
            content: List of content blocks
            
        Returns:
            Plain text string
        """
        texts = []
        
        for block in content:
            block_type = block.get("type", "")
            block_content = block.get("content", "")
            
            if isinstance(block_content, str):
                texts.append(block_content)
            elif isinstance(block_content, list):
                # Handle nested content (e.g., rich text)
                for item in block_content:
                    if isinstance(item, str):
                        texts.append(item)
                    elif isinstance(item, dict):
                        texts.append(item.get("text", ""))
        
        return " ".join(texts)
    
    def _extract_concept_links(self, content: list[dict]) -> list[str]:
        """
        Extract [[concept]] links from content.
        
        Args:
            content: List of content blocks
            
        Returns:
            List of concept labels/URIs
        """
        concepts = []
        pattern = r'\[\[([^\]]+)\]\]'
        
        plain_text = self._extract_plain_text(content)
        matches = re.findall(pattern, plain_text)
        
        for match in matches:
            # Normalize concept label
            concept = match.strip().lower()
            if concept and concept not in concepts:
                concepts.append(concept)
        
        return concepts

