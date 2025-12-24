"""
SQLAlchemy domain models for the Synaptiq application.

Contains:
- User: Core user entity with auth info
- UserSettings: User preferences and configuration
- Session: Refresh token sessions for auth

Compatible with both SQLAlchemy 1.4 and 2.0.
"""

from datetime import datetime, timezone
from typing import Optional, List
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
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
