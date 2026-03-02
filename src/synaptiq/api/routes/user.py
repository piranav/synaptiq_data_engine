"""
User API routes.

Provides endpoints for:
- User profile management
- User settings
- User statistics
- Data export (GDPR)
- Account deletion (GDPR)
"""

from typing import Optional, Any
import asyncio

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from synaptiq.api.middleware.auth import get_current_user
from synaptiq.api.dependencies import get_mongodb
from synaptiq.domain.models import User
from synaptiq.infrastructure.database import get_async_session
from synaptiq.services.user_service import UserService
from synaptiq.storage.mongodb import MongoDBStore

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/user", tags=["user"])


# =============================================================================
# REQUEST/RESPONSE SCHEMAS
# =============================================================================


class UserProfileResponse(BaseModel):
    """User profile information."""
    
    id: str
    email: str
    name: Optional[str]
    avatar_url: Optional[str]
    graph_uri: Optional[str]
    is_verified: bool
    created_at: str


class UpdateProfileRequest(BaseModel):
    """Request to update user profile."""
    
    name: Optional[str] = Field(None, max_length=255)
    avatar_url: Optional[str] = Field(None, max_length=500)


class UserSettingsResponse(BaseModel):
    """User settings."""
    
    theme: str
    accent_color: str
    sidebar_collapsed: bool
    density: str
    processing_mode: str
    analytics_opt_in: bool


class UpdateSettingsRequest(BaseModel):
    """Request to update settings."""
    
    theme: Optional[str] = Field(None, pattern="^(light|dark|system)$")
    accent_color: Optional[str] = Field(None, pattern="^#[0-9A-Fa-f]{6}$")
    sidebar_collapsed: Optional[bool] = None
    density: Optional[str] = Field(None, pattern="^(comfortable|compact)$")
    processing_mode: Optional[str] = Field(None, pattern="^(cloud|on_device)$")
    analytics_opt_in: Optional[bool] = None


class SaveApiKeysRequest(BaseModel):
    """Request to save API keys (empty string clears the key)."""

    openai_api_key: Optional[str] = Field(None, description="OpenAI API key")
    anthropic_api_key: Optional[str] = Field(None, description="Anthropic API key")


class ApiKeysResponse(BaseModel):
    """Masked API key status."""

    openai_api_key_set: bool
    openai_api_key_masked: str
    anthropic_api_key_set: bool
    anthropic_api_key_masked: str


class UserStatsResponse(BaseModel):
    """User knowledge base statistics."""
    
    concepts_count: int
    sources_count: int
    chunks_count: int
    definitions_count: int
    relationships_count: int
    graph_uri: Optional[str]
    growth_percent: Optional[float] = None


class MessageResponse(BaseModel):
    """Generic message response."""
    
    message: str


class DeleteAccountResponse(BaseModel):
    """Response from account deletion."""
    
    message: str
    deleted: dict


# =============================================================================
# ENDPOINTS
# =============================================================================


@router.get(
    "/profile",
    response_model=UserProfileResponse,
    summary="Get user profile",
)
async def get_profile(
    user: User = Depends(get_current_user),
):
    """
    Get the current user's profile information.
    """
    return UserProfileResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        avatar_url=user.avatar_url,
        graph_uri=user.graph_uri,
        is_verified=user.is_verified,
        created_at=user.created_at.isoformat(),
    )


@router.patch(
    "/profile",
    response_model=UserProfileResponse,
    summary="Update user profile",
)
async def update_profile(
    body: UpdateProfileRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Update the current user's profile information.
    """
    user_service = UserService(session)
    
    updated_user = await user_service.update_user(
        user_id=user.id,
        name=body.name,
        avatar_url=body.avatar_url,
    )
    
    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    return UserProfileResponse(
        id=updated_user.id,
        email=updated_user.email,
        name=updated_user.name,
        avatar_url=updated_user.avatar_url,
        graph_uri=updated_user.graph_uri,
        is_verified=updated_user.is_verified,
        created_at=updated_user.created_at.isoformat(),
    )


@router.get(
    "/settings",
    response_model=UserSettingsResponse,
    summary="Get user settings",
)
async def get_settings(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Get the current user's settings.
    """
    user_service = UserService(session)
    settings = await user_service.get_user_settings(user.id)
    
    if not settings:
        # Return defaults if no settings exist
        return UserSettingsResponse(
            theme="system",
            accent_color="#0066CC",
            sidebar_collapsed=False,
            density="comfortable",
            processing_mode="cloud",
            analytics_opt_in=False,
        )
    
    return UserSettingsResponse(
        theme=settings.theme,
        accent_color=settings.accent_color,
        sidebar_collapsed=settings.sidebar_collapsed,
        density=settings.density,
        processing_mode=settings.processing_mode,
        analytics_opt_in=settings.analytics_opt_in,
    )


@router.patch(
    "/settings",
    response_model=UserSettingsResponse,
    summary="Update user settings",
)
async def update_settings(
    body: UpdateSettingsRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Update the current user's settings.
    """
    user_service = UserService(session)
    
    settings = await user_service.update_settings(
        user_id=user.id,
        theme=body.theme,
        accent_color=body.accent_color,
        sidebar_collapsed=body.sidebar_collapsed,
        density=body.density,
        processing_mode=body.processing_mode,
        analytics_opt_in=body.analytics_opt_in,
    )
    
    return UserSettingsResponse(
        theme=settings.theme,
        accent_color=settings.accent_color,
        sidebar_collapsed=settings.sidebar_collapsed,
        density=settings.density,
        processing_mode=settings.processing_mode,
        analytics_opt_in=settings.analytics_opt_in,
    )


@router.get(
    "/api-keys",
    response_model=ApiKeysResponse,
    summary="Get masked API key status",
)
async def get_api_keys(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> ApiKeysResponse:
    """Return masked versions of the user's stored API keys."""
    user_service = UserService(session)
    try:
        result = await user_service.get_api_keys_masked(user.id)
    except Exception as e:
        if "does not exist" in str(e):
            logger.warning("API key columns missing – run: alembic upgrade head")
            return ApiKeysResponse(
                openai_api_key_set=False, openai_api_key_masked="",
                anthropic_api_key_set=False, anthropic_api_key_masked="",
            )
        raise
    return ApiKeysResponse(**result)


@router.put(
    "/api-keys",
    response_model=ApiKeysResponse,
    summary="Save API keys (encrypted)",
)
async def save_api_keys(
    body: SaveApiKeysRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> ApiKeysResponse:
    """Encrypt and save the user's API keys. Pass empty string to clear a key."""
    user_service = UserService(session)
    try:
        result = await user_service.save_api_keys(
            user_id=user.id,
            openai_api_key=body.openai_api_key,
            anthropic_api_key=body.anthropic_api_key,
        )
    except Exception as e:
        if "does not exist" in str(e):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database migration pending. Run: alembic upgrade head",
            )
        raise
    return ApiKeysResponse(**result)


@router.get(
    "/stats",
    response_model=UserStatsResponse,
    summary="Get knowledge base statistics",
)
async def get_stats(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Get statistics about the user's knowledge base.
    
    Returns counts of concepts, sources, chunks, etc.
    """
    user_service = UserService(session)
    
    try:
        stats = await user_service.get_user_stats(user.id)
        return UserStatsResponse(**stats.to_dict())
    finally:
        await user_service.close()


class DashboardResponse(BaseModel):
    """Combined dashboard data response."""
    
    stats: UserStatsResponse
    recent_sources: list[dict[str, Any]] = Field(default_factory=list)
    active_jobs: list[dict[str, Any]] = Field(default_factory=list)


@router.get(
    "/dashboard",
    response_model=DashboardResponse,
    summary="Get combined dashboard data",
    description="Returns stats, recent sources, and jobs in a single request for faster dashboard loading.",
)
async def get_dashboard(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    mongodb: MongoDBStore = Depends(get_mongodb),
):
    """
    Get combined dashboard data in a single request.
    
    This endpoint fetches stats, recent sources, and active jobs in parallel
    to reduce dashboard loading time (replaces 3 sequential API calls).
    """
    user_service = UserService(session)
    
    try:
        # Fetch all data in parallel
        stats_task = user_service.get_user_stats(user.id)
        sources_task = mongodb.list_sources(user.id, limit=5)
        jobs_task = mongodb.list_jobs(user.id, limit=5)
        
        stats, sources, jobs = await asyncio.gather(
            stats_task,
            sources_task,
            jobs_task,
            return_exceptions=True,
        )
        
        # Handle any errors gracefully
        if isinstance(stats, Exception):
            logger.warning("Failed to get stats", error=str(stats))
            stats = UserStatsResponse(
                concepts_count=0, sources_count=0, chunks_count=0,
                definitions_count=0, relationships_count=0, graph_uri=None,
                growth_percent=None,
            )
        else:
            stats = UserStatsResponse(**stats.to_dict())
        
        if isinstance(sources, Exception):
            logger.warning("Failed to get sources", error=str(sources))
            sources = []
        else:
            # Format sources for response
            sources = [
                {
                    "id": s["id"],
                    "type": s.get("source_type", "unknown"),
                    "title": s.get("source_title", "Untitled"),
                    "url": s.get("source_url", ""),
                    "time": s.get("ingested_at").isoformat() if hasattr(s.get("ingested_at"), "isoformat") else str(s.get("ingested_at", "")),
                }
                for s in sources
            ]
        
        if isinstance(jobs, Exception):
            logger.warning("Failed to get jobs", error=str(jobs))
            jobs = []
        else:
            jobs = [
                {
                    "id": j.id,
                    "status": j.status.value if hasattr(j.status, "value") else str(j.status),
                    "source_type": j.source_type,
                    "source_url": j.source_url,
                    "created_at": j.created_at.isoformat() if hasattr(j.created_at, "isoformat") else str(j.created_at),
                }
                for j in jobs
            ]
        
        return DashboardResponse(
            stats=stats,
            recent_sources=sources,
            active_jobs=jobs,
        )
    finally:
        await user_service.close()

@router.post(
    "/export",
    summary="Export all user data",
    responses={
        200: {"description": "User data export"},
    },
)
async def export_data(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Export all user data (GDPR data portability).
    
    Returns a JSON object containing:
    - User profile
    - Settings
    - Knowledge graph (Turtle format)
    - Statistics
    """
    user_service = UserService(session)
    
    try:
        export = await user_service.export_user_data(user.id)
        return export
    finally:
        await user_service.close()


@router.delete(
    "/",
    response_model=DeleteAccountResponse,
    summary="Delete account",
)
async def delete_account(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Delete the user's account and all associated data.
    
    This action is irreversible and removes:
    - User profile and settings
    - All sessions
    - Knowledge graph
    - Vector embeddings
    
    GDPR right to erasure.
    """
    user_service = UserService(session)
    
    try:
        result = await user_service.delete_user(user.id)
        return DeleteAccountResponse(
            message="Account deleted successfully",
            deleted=result.get("deleted", {}),
        )
    finally:
        await user_service.close()


@router.post(
    "/provision-graph",
    response_model=MessageResponse,
    summary="Provision knowledge graph",
)
async def provision_graph(
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Manually trigger knowledge graph provisioning.
    
    This is normally done automatically on signup, but can be
    used to retry if initial provisioning failed.
    """
    if user.graph_uri:
        return MessageResponse(
            message=f"Knowledge graph already provisioned: {user.graph_uri}"
        )
    
    user_service = UserService(session)
    
    try:
        graph_uri = await user_service.provision_knowledge_space(user.id)
        return MessageResponse(
            message=f"Knowledge graph provisioned: {graph_uri}"
        )
    except Exception as e:
        logger.error("Graph provisioning failed", user_id=user.id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to provision knowledge graph: {str(e)}",
        )
    finally:
        await user_service.close()
