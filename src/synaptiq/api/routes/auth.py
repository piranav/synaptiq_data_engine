"""
Authentication API routes.

Provides endpoints for:
- User registration (signup)
- Login and token generation
- Token refresh
- Logout
- Password reset
- Current user info
"""

from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from synaptiq.infrastructure.database import get_async_session
from synaptiq.services.auth_service import AuthError, AuthService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


# =============================================================================
# REQUEST/RESPONSE SCHEMAS
# =============================================================================


class SignupRequest(BaseModel):
    """Request body for user registration."""
    
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(
        ...,
        min_length=8,
        description="Password (minimum 8 characters)",
    )
    name: Optional[str] = Field(None, max_length=255, description="Display name")


class LoginRequest(BaseModel):
    """Request body for login."""
    
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., description="Password")


class TokenResponse(BaseModel):
    """Response containing authentication tokens."""
    
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")


class RefreshRequest(BaseModel):
    """Request body for token refresh."""
    
    refresh_token: str = Field(..., description="Refresh token")


class UserResponse(BaseModel):
    """Response containing user information."""
    
    id: str = Field(..., description="User ID")
    email: str = Field(..., description="Email address")
    name: Optional[str] = Field(None, description="Display name")
    avatar_url: Optional[str] = Field(None, description="Avatar URL")
    graph_uri: Optional[str] = Field(None, description="Knowledge graph URI")
    is_verified: bool = Field(..., description="Email verified status")
    created_at: str = Field(..., description="Account creation timestamp")


class AuthResponse(BaseModel):
    """Response for successful authentication."""
    
    user: UserResponse
    tokens: TokenResponse


class ForgotPasswordRequest(BaseModel):
    """Request body for forgot password."""
    
    email: EmailStr = Field(..., description="User's email address")


class ResetPasswordRequest(BaseModel):
    """Request body for password reset."""
    
    token: str = Field(..., description="Password reset token")
    new_password: str = Field(
        ...,
        min_length=8,
        description="New password (minimum 8 characters)",
    )


class MessageResponse(BaseModel):
    """Generic message response."""
    
    message: str


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def get_client_info(request: Request) -> tuple[Optional[str], Optional[str]]:
    """Extract user agent and IP address from request."""
    user_agent = request.headers.get("user-agent")
    
    # Get IP from X-Forwarded-For if behind proxy
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        ip_address = forwarded_for.split(",")[0].strip()
    else:
        ip_address = request.client.host if request.client else None
    
    return user_agent, ip_address


def user_to_response(user) -> UserResponse:
    """Convert User model to response schema."""
    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        avatar_url=user.avatar_url,
        graph_uri=user.graph_uri,
        is_verified=user.is_verified,
        created_at=user.created_at.isoformat(),
    )


# =============================================================================
# ENDPOINTS
# =============================================================================


@router.post(
    "/signup",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new account",
    responses={
        400: {"description": "Invalid input or email already exists"},
    },
)
async def signup(
    request: Request,
    body: SignupRequest,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Create a new user account with email and password.
    
    Returns authentication tokens upon successful registration.
    The user's knowledge graph will be provisioned asynchronously.
    """
    user_agent, ip_address = get_client_info(request)
    
    auth_service = AuthService(session)
    
    try:
        user, token_pair = await auth_service.signup(
            email=body.email,
            password=body.password,
            name=body.name,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        
        return AuthResponse(
            user=user_to_response(user),
            tokens=TokenResponse(**token_pair.to_dict()),
        )
        
    except AuthError as e:
        logger.warning("Signup failed", email=body.email, error=e.code)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": e.message, "code": e.code},
        )


@router.post(
    "/login",
    response_model=AuthResponse,
    summary="Login with email and password",
    responses={
        401: {"description": "Invalid credentials"},
    },
)
async def login(
    request: Request,
    body: LoginRequest,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Authenticate with email and password.
    
    Returns access and refresh tokens upon successful authentication.
    """
    user_agent, ip_address = get_client_info(request)
    
    auth_service = AuthService(session)
    
    try:
        user, token_pair = await auth_service.login(
            email=body.email,
            password=body.password,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        
        return AuthResponse(
            user=user_to_response(user),
            tokens=TokenResponse(**token_pair.to_dict()),
        )
        
    except AuthError as e:
        logger.warning("Login failed", email=body.email, error=e.code)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message": e.message, "code": e.code},
        )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
    responses={
        401: {"description": "Invalid or expired refresh token"},
    },
)
async def refresh_token(
    request: Request,
    body: RefreshRequest,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Get a new access token using a refresh token.
    
    The old refresh token is invalidated and a new one is returned.
    """
    user_agent, ip_address = get_client_info(request)
    
    auth_service = AuthService(session)
    
    try:
        token_pair = await auth_service.refresh_token(
            refresh_token=body.refresh_token,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        
        return TokenResponse(**token_pair.to_dict())
        
    except AuthError as e:
        logger.warning("Token refresh failed", error=e.code)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message": e.message, "code": e.code},
        )


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Logout and invalidate session",
)
async def logout(
    body: RefreshRequest,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Logout by invalidating the refresh token.
    
    The access token will remain valid until it expires,
    but the refresh token can no longer be used.
    """
    auth_service = AuthService(session)
    
    deleted = await auth_service.logout(body.refresh_token)
    
    if deleted:
        return MessageResponse(message="Successfully logged out")
    else:
        return MessageResponse(message="Session not found or already logged out")


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    summary="Request password reset",
)
async def forgot_password(
    body: ForgotPasswordRequest,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Request a password reset email.
    
    If the email exists, a reset link will be sent.
    For security, the response is the same whether the email exists or not.
    """
    auth_service = AuthService(session)
    
    # Note: In production, this should send an email
    # For now, we just return success regardless
    await auth_service.initiate_password_reset(body.email)
    
    return MessageResponse(
        message="If an account with that email exists, a password reset link has been sent."
    )


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    summary="Reset password with token",
    responses={
        400: {"description": "Invalid token or password"},
    },
)
async def reset_password(
    body: ResetPasswordRequest,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Reset password using a reset token.
    
    After successful reset, all existing sessions are invalidated.
    """
    auth_service = AuthService(session)
    
    try:
        await auth_service.reset_password(
            reset_token=body.token,
            new_password=body.new_password,
        )
        
        return MessageResponse(message="Password has been reset successfully")
        
    except AuthError as e:
        logger.warning("Password reset failed", error=e.code)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": e.message, "code": e.code},
        )


# =============================================================================
# AUTHENTICATED ENDPOINTS (require middleware)
# =============================================================================
# Note: The /me endpoint is defined here but requires the auth middleware
# to inject the current user. It will be connected after middleware is created.


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user",
    responses={
        401: {"description": "Not authenticated"},
    },
)
async def get_current_user_info(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Get the currently authenticated user's information.
    
    Requires a valid access token in the Authorization header.
    """
    # This will be populated by the auth middleware
    user = getattr(request.state, "user", None)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message": "Not authenticated", "code": "not_authenticated"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user_to_response(user)

