"""
PostgreSQL database configuration with SQLAlchemy async support.

Provides async engine, session factory, and dependency injection
for FastAPI routes.

Compatible with both SQLAlchemy 1.4 and 2.0.
"""

from typing import AsyncGenerator

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Try SQLAlchemy 2.0 style, fall back to 1.4
try:
    from sqlalchemy.orm import DeclarativeBase
    
    class Base(DeclarativeBase):
        """Base class for all SQLAlchemy models."""
        pass
except ImportError:
    from sqlalchemy.ext.declarative import declarative_base
    Base = declarative_base()

# Try async_sessionmaker (SQLAlchemy 2.0), fall back to sessionmaker
try:
    from sqlalchemy.ext.asyncio import async_sessionmaker
    HAS_ASYNC_SESSIONMAKER = True
except ImportError:
    HAS_ASYNC_SESSIONMAKER = False

from config.settings import get_settings

logger = structlog.get_logger(__name__)


# Global engine and session factory (lazy initialized)
_engine = None
_async_session_factory = None


def get_engine():
    """
    Get or create the async database engine.
    
    Returns:
        AsyncEngine: SQLAlchemy async engine
    """
    global _engine
    
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.postgres_url,
            echo=settings.log_level == "DEBUG",
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
        )
        logger.info(
            "Database engine created",
            url=settings.postgres_url.split("@")[-1],  # Hide credentials
        )
    
    return _engine


def get_session_factory():
    """
    Get or create the async session factory.
    
    Returns:
        Session factory for creating async sessions
    """
    global _async_session_factory
    
    if _async_session_factory is None:
        engine = get_engine()
        
        if HAS_ASYNC_SESSIONMAKER:
            # SQLAlchemy 2.0+
            _async_session_factory = async_sessionmaker(
                engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autocommit=False,
                autoflush=False,
            )
        else:
            # SQLAlchemy 1.4
            _async_session_factory = sessionmaker(
                engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autocommit=False,
                autoflush=False,
            )
    
    return _async_session_factory


# Alias for backwards compatibility and convenience
AsyncSessionLocal = property(lambda self: get_session_factory())


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency that provides an async database session.
    
    Use as a FastAPI dependency:
    
    ```python
    @router.get("/users")
    async def get_users(session: AsyncSession = Depends(get_async_session)):
        ...
    ```
    
    Yields:
        AsyncSession: Database session that auto-commits on success
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """
    Initialize the database by creating all tables.
    
    Note: In production, use Alembic migrations instead.
    This is useful for development and testing.
    """
    engine = get_engine()
    
    async with engine.begin() as conn:
        # Import models to ensure they're registered with Base
        from synaptiq.domain import models  # noqa: F401
        
        await conn.run_sync(Base.metadata.create_all)
    
    logger.info("Database tables created")


async def close_db() -> None:
    """
    Close the database engine and cleanup connections.
    
    Call this during application shutdown.
    """
    global _engine, _async_session_factory
    
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _async_session_factory = None
        logger.info("Database connection closed")

