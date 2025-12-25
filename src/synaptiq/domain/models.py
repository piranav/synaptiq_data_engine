"""
SQLAlchemy domain models for the Synaptiq application.

Contains:
- User: Core user entity with auth info
- UserSettings: User preferences and configuration
- Session: Refresh token sessions for auth
- Conversation: Chat conversation container
- Message: Individual chat messages
- Folder: Note organization folders
- Note: User-created notes with concept linking

Compatible with both SQLAlchemy 1.4 and 2.0.
"""

from datetime import datetime, timezone
from typing import Optional, List
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from synaptiq.infrastructure.database import Base


def utc_now() -> datetime:
    """Get current UTC datetime."""
    return datetime.now(timezone.utc)


def generate_uuid() -> str:
    """Generate a new UUID string."""
    return str(uuid4())


class User(Base):
    """
    Core user entity.
    
    Stores authentication information and links to the user's
    knowledge graph in Fuseki.
    """
    
    __tablename__ = "users"
    
    # Primary key
    id = Column(
        UUID(as_uuid=False),
        primary_key=True,
        default=generate_uuid,
    )
    
    # Authentication
    email = Column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    password_hash = Column(
        String(255),
        nullable=True,  # Null for OAuth-only users
    )
    
    # Profile
    name = Column(String(255), nullable=True)
    avatar_url = Column(String(500), nullable=True)
    
    # Knowledge graph link
    graph_uri = Column(
        String(255),
        nullable=True,  # Set after graph provisioning
    )
    
    # OAuth fields
    oauth_provider = Column(
        String(50),
        nullable=True,  # 'google', 'github', etc.
    )
    oauth_id = Column(String(255), nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    
    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
        nullable=False,
    )
    
    # Relationships
    settings = relationship(
        "UserSettings",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    sessions = relationship(
        "Session",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    conversations = relationship(
        "Conversation",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    folders = relationship(
        "Folder",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    notes = relationship(
        "Note",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    
    # Indexes
    __table_args__ = (
        Index("ix_users_oauth", "oauth_provider", "oauth_id"),
    )
    
    def __repr__(self) -> str:
        return f"<User {self.email}>"


class UserSettings(Base):
    """
    User preferences and configuration.
    
    One-to-one relationship with User.
    """
    
    __tablename__ = "user_settings"
    
    # Foreign key as primary key (one-to-one)
    user_id = Column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    
    # Appearance
    theme = Column(
        String(20),
        default="system",  # 'light', 'dark', 'system'
        nullable=False,
    )
    accent_color = Column(
        String(7),
        default="#0066CC",
        nullable=False,
    )
    
    # UI preferences
    sidebar_collapsed = Column(Boolean, default=False, nullable=False)
    density = Column(
        String(20),
        default="comfortable",  # 'comfortable', 'compact'
        nullable=False,
    )
    
    # Processing preferences
    processing_mode = Column(
        String(20),
        default="cloud",  # 'cloud', 'on_device'
        nullable=False,
    )
    
    # Privacy
    analytics_opt_in = Column(Boolean, default=False, nullable=False)
    
    # Timestamps
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
        nullable=False,
    )
    
    # Relationships
    user = relationship("User", back_populates="settings")
    
    def __repr__(self) -> str:
        return f"<UserSettings user_id={self.user_id}>"


class Session(Base):
    """
    Refresh token session for authentication.
    
    Stores refresh tokens with expiration for token refresh flow.
    Multiple sessions per user are allowed (multi-device support).
    """
    
    __tablename__ = "sessions"
    
    # Primary key
    id = Column(
        UUID(as_uuid=False),
        primary_key=True,
        default=generate_uuid,
    )
    
    # Foreign key
    user_id = Column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Token
    refresh_token = Column(
        String(500),
        unique=True,
        nullable=False,
        index=True,
    )
    
    # Expiration
    expires_at = Column(DateTime(timezone=True), nullable=False)
    
    # Device info (optional)
    user_agent = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)  # IPv6 max length
    
    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=func.now(),
        nullable=False,
    )
    
    # Relationships
    user = relationship("User", back_populates="sessions")
    
    @property
    def is_expired(self) -> bool:
        """Check if the session has expired."""
        return datetime.now(timezone.utc) > self.expires_at
    
    def __repr__(self) -> str:
        return f"<Session {self.id} user_id={self.user_id}>"


# =============================================================================
# CONVERSATION & CHAT MODELS
# =============================================================================


class Conversation(Base):
    """
    Chat conversation container.
    
    Groups messages into conversation threads for the chat interface.
    Each user can have multiple conversations.
    """
    
    __tablename__ = "conversations"
    
    # Primary key
    id = Column(
        UUID(as_uuid=False),
        primary_key=True,
        default=generate_uuid,
    )
    
    # Foreign key
    user_id = Column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Conversation metadata
    title = Column(
        String(500),
        nullable=True,  # Auto-generated from first message if not set
    )
    preview = Column(
        String(200),
        nullable=True,  # First ~200 chars of first message
    )
    
    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
        nullable=False,
    )
    
    # Relationships
    user = relationship("User", back_populates="conversations")
    messages = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )
    
    # Indexes
    __table_args__ = (
        Index("ix_conversations_user_updated", "user_id", "updated_at"),
    )
    
    def __repr__(self) -> str:
        return f"<Conversation {self.id} user_id={self.user_id}>"


class Message(Base):
    """
    Individual chat message.
    
    Stores user queries and assistant responses with citations
    and metadata about the retrieval process.
    """
    
    __tablename__ = "messages"
    
    # Primary key
    id = Column(
        UUID(as_uuid=False),
        primary_key=True,
        default=generate_uuid,
    )
    
    # Foreign key
    conversation_id = Column(
        UUID(as_uuid=False),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Message content
    role = Column(
        String(20),
        nullable=False,  # 'user' or 'assistant'
    )
    content = Column(
        Text,
        nullable=False,
    )
    
    # Assistant response metadata (null for user messages)
    citations = Column(
        JSONB,
        default=list,
        server_default="[]",
        nullable=False,
    )
    concepts_referenced = Column(
        JSONB,
        default=list,
        server_default="[]",
        nullable=False,
    )
    retrieval_metadata = Column(
        JSONB,
        nullable=True,  # Strategy, source, confidence, etc.
    )
    confidence = Column(
        Float,
        nullable=True,  # 0.0 - 1.0 for assistant responses
    )
    source_type = Column(
        String(50),
        nullable=True,  # 'personal_knowledge', 'llm_knowledge', 'error'
    )
    
    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=func.now(),
        nullable=False,
    )
    
    # Relationships
    conversation = relationship("Conversation", back_populates="messages")
    
    # Indexes
    __table_args__ = (
        Index("ix_messages_conversation_created", "conversation_id", "created_at"),
    )
    
    def __repr__(self) -> str:
        return f"<Message {self.id} role={self.role}>"


# =============================================================================
# NOTES & FOLDERS MODELS
# =============================================================================


class Folder(Base):
    """
    Note organization folder.
    
    Supports hierarchical folder structure with parent-child relationships.
    """
    
    __tablename__ = "folders"
    
    # Primary key
    id = Column(
        UUID(as_uuid=False),
        primary_key=True,
        default=generate_uuid,
    )
    
    # Foreign keys
    user_id = Column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parent_id = Column(
        UUID(as_uuid=False),
        ForeignKey("folders.id", ondelete="CASCADE"),
        nullable=True,  # Null for root-level folders
        index=True,
    )
    
    # Folder info
    name = Column(
        String(255),
        nullable=False,
    )
    
    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
        nullable=False,
    )
    
    # Relationships
    user = relationship("User", back_populates="folders")
    parent = relationship(
        "Folder",
        remote_side=[id],
        backref="children",
    )
    notes = relationship(
        "Note",
        back_populates="folder",
        cascade="all, delete-orphan",
    )
    
    def __repr__(self) -> str:
        return f"<Folder {self.id} name={self.name}>"


class Note(Base):
    """
    User-created note with concept linking.
    
    Stores block-based content (similar to Notion) with
    links to concepts in the knowledge graph.
    """
    
    __tablename__ = "notes"
    
    # Primary key
    id = Column(
        UUID(as_uuid=False),
        primary_key=True,
        default=generate_uuid,
    )
    
    # Foreign keys
    user_id = Column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    folder_id = Column(
        UUID(as_uuid=False),
        ForeignKey("folders.id", ondelete="SET NULL"),
        nullable=True,  # Null for unfiled notes
        index=True,
    )
    
    # Note content
    title = Column(
        String(500),
        nullable=False,
        default="Untitled",
    )
    content = Column(
        JSONB,
        nullable=False,
        default=list,  # Block-based content structure
        server_default="[]",
    )
    plain_text = Column(
        Text,
        nullable=True,  # Extracted text for search
    )
    
    # Knowledge graph integration
    linked_concepts = Column(
        JSONB,
        default=list,
        server_default="[]",
        nullable=False,  # Concept URIs from the graph
    )
    
    # Statistics
    word_count = Column(
        Integer,
        default=0,
        nullable=False,
    )
    
    # Processing state
    last_extracted_at = Column(
        DateTime(timezone=True),
        nullable=True,  # When concepts were last extracted
    )
    
    # Status
    is_archived = Column(
        Boolean,
        default=False,
        nullable=False,
    )
    is_pinned = Column(
        Boolean,
        default=False,
        nullable=False,
    )
    
    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
        nullable=False,
    )
    
    # Relationships
    user = relationship("User", back_populates="notes")
    folder = relationship("Folder", back_populates="notes")
    
    # Indexes
    __table_args__ = (
        Index("ix_notes_user_updated", "user_id", "updated_at"),
        Index("ix_notes_user_folder", "user_id", "folder_id"),
    )
    
    def __repr__(self) -> str:
        return f"<Note {self.id} title={self.title[:30]}>"
