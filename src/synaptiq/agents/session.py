"""
Session management for agent conversations.

Uses SQLAlchemy sessions from the OpenAI Agents SDK for persistent
conversation history in PostgreSQL.
"""

from typing import Optional
import structlog

from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine

logger = structlog.get_logger(__name__)

# Global engine cache
_engine: Optional[AsyncEngine] = None


def create_session_engine(postgres_url: Optional[str] = None) -> AsyncEngine:
    """
    Create or get the SQLAlchemy async engine.
    
    Args:
        postgres_url: PostgreSQL connection URL (uses settings if not provided)
        
    Returns:
        AsyncEngine instance
    """
    global _engine
    
    if _engine is None:
        if postgres_url is None:
            from config.settings import get_settings
            settings = get_settings()
            postgres_url = settings.postgres_url
        
        _engine = create_async_engine(
            postgres_url,
            echo=False,
            pool_size=5,
            max_overflow=10,
        )
        
        logger.info("Created session engine", url=postgres_url.split("@")[-1])
    
    return _engine


async def get_session(session_id: str, user_id: str):
    """
    Get or create a session for a user conversation.
    
    Sessions are scoped by combining user_id and session_id to ensure
    multi-tenant isolation. Sessions persist indefinitely.
    
    Args:
        session_id: Conversation session identifier
        user_id: User identifier for isolation
        
    Returns:
        SQLAlchemySession instance
    """
    from agents.extensions.memory import SQLAlchemySession
    
    engine = create_session_engine()
    
    # Combine user_id and session_id for multi-tenant isolation
    full_session_id = f"{user_id}:{session_id}"
    
    session = SQLAlchemySession(
        full_session_id,
        engine=engine,
        create_tables=True,
    )
    
    logger.debug(
        "Got session",
        session_id=session_id,
        user_id=user_id,
        full_session_id=full_session_id,
    )
    
    return session


async def list_user_sessions(user_id: str) -> list[str]:
    """
    List all session IDs for a user.
    
    Args:
        user_id: User identifier
        
    Returns:
        List of session IDs (without user prefix)
    """
    from sqlalchemy import text
    
    engine = create_session_engine()
    
    async with engine.begin() as conn:
        # Query the sessions table for this user's sessions
        result = await conn.execute(
            text(
                """
                SELECT DISTINCT session_id 
                FROM agent_sessions 
                WHERE session_id LIKE :pattern
                ORDER BY session_id
                """
            ),
            {"pattern": f"{user_id}:%"},
        )
        
        rows = result.fetchall()
        
    # Strip user_id prefix from session IDs
    prefix = f"{user_id}:"
    return [row[0][len(prefix):] for row in rows if row[0].startswith(prefix)]


async def delete_session(session_id: str, user_id: str) -> bool:
    """
    Delete a conversation session.
    
    Args:
        session_id: Conversation session identifier
        user_id: User identifier
        
    Returns:
        True if session was deleted
    """
    from sqlalchemy import text
    
    engine = create_session_engine()
    full_session_id = f"{user_id}:{session_id}"
    
    async with engine.begin() as conn:
        result = await conn.execute(
            text("DELETE FROM agent_sessions WHERE session_id = :session_id"),
            {"session_id": full_session_id},
        )
        
    deleted = result.rowcount > 0
    
    logger.info(
        "Deleted session",
        session_id=session_id,
        user_id=user_id,
        deleted=deleted,
    )
    
    return deleted


async def close_session_engine() -> None:
    """Close the session engine connection pool."""
    global _engine
    
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        logger.info("Closed session engine")
