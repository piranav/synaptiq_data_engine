"""
JWT Authentication middleware and dependencies.

Provides:
- AuthMiddleware: FastAPI middleware that attaches user to request state
- get_current_user: Dependency that requires authentication
- get_current_user_optional: Dependency that allows anonymous access
"""

from typing import Optional

import structlog
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from synaptiq.domain.models import User
from synaptiq.infrastructure.database import get_async_session, get_session_factory
from synaptiq.services.auth_service import AuthService

logger = structlog.get_logger(__name__)

# HTTP Bearer scheme for extracting JWT from Authorization header
http_bearer = HTTPBearer(auto_error=False)


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware that validates JWT tokens and attaches user to request state.
    
    This middleware runs for all requests and attempts to extract and validate
    the JWT token from the Authorization header. If valid, the user is attached
    to `request.state.user`.
    
    Routes can then use `get_current_user` or `get_current_user_optional`
    dependencies to access the authenticated user.
    """
    
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """Process the request and attach user if authenticated."""
        # Initialize user as None
        request.state.user = None
        
        # Extract token from Authorization header
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]  # Remove "Bearer " prefix
            
            # Validate token and get user
            session_factory = get_session_factory()
            async with session_factory() as session:
                try:
                    auth_service = AuthService(session)
                    user = await auth_service.verify_access_token(token)
                    if user:
                        request.state.user = user
                        request.state.user_id = user.id
                except Exception as e:
                    logger.warning("Auth middleware error", error=str(e))
        
        response = await call_next(request)
        return response


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
    session: AsyncSession = Depends(get_async_session),
) -> User:
    """
    FastAPI dependency that requires a valid JWT token.
    
    Use this dependency to protect routes that require authentication:
    
    ```python
    @router.get("/protected")
    async def protected_route(user: User = Depends(get_current_user)):
        return {"user_id": user.id}
    ```
    
    Args:
        request: FastAPI request object
        credentials: HTTP Bearer credentials from Authorization header
        session: Database session
        
    Returns:
        Authenticated User object
        
    Raises:
        HTTPException: If not authenticated or token is invalid
    """
    # First check if middleware already attached user
    user = getattr(request.state, "user", None)
    if user:
        return user
    
    # If no credentials provided
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "message": "Authentication required",
                "code": "not_authenticated",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Validate token
    auth_service = AuthService(session)
    user = await auth_service.verify_access_token(credentials.credentials)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "message": "Invalid or expired token",
                "code": "invalid_token",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Store user in request state for other dependencies
    request.state.user = user
    request.state.user_id = user.id
    
    return user


async def get_current_user_optional(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
    session: AsyncSession = Depends(get_async_session),
) -> Optional[User]:
    """
    FastAPI dependency that optionally authenticates.
    
    Use this dependency for routes that work with or without authentication:
    
    ```python
    @router.get("/public")
    async def public_route(user: Optional[User] = Depends(get_current_user_optional)):
        if user:
            return {"message": f"Hello, {user.name}!"}
        return {"message": "Hello, guest!"}
    ```
    
    Args:
        request: FastAPI request object
        credentials: HTTP Bearer credentials (may be None)
        session: Database session
        
    Returns:
        User if authenticated, None otherwise
    """
    # Check if middleware already attached user
    user = getattr(request.state, "user", None)
    if user:
        return user
    
    # If no credentials, return None (anonymous access)
    if not credentials:
        return None
    
    # Try to validate token
    auth_service = AuthService(session)
    user = await auth_service.verify_access_token(credentials.credentials)
    
    if user:
        request.state.user = user
        request.state.user_id = user.id
    
    return user


def get_user_id(request: Request) -> str:
    """
    Simple dependency to get user_id from request state.
    
    Use after get_current_user to just get the user_id string:
    
    ```python
    @router.get("/data")
    async def get_data(
        user: User = Depends(get_current_user),
        user_id: str = Depends(get_user_id),
    ):
        # user_id is a string, user is the full User object
        ...
    ```
    """
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message": "Not authenticated", "code": "not_authenticated"},
        )
    return user_id

