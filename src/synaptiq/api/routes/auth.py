"""
Authentication API routes.

Provides endpoints for:
- User registration (signup)
- Login and token generation
- Social OAuth (Google, GitHub)
- Token refresh
- Logout
- Password reset
- Current user info
"""

from datetime import datetime, timedelta, timezone
import json
from typing import Any, Literal, Optional
from urllib.parse import urlencode
from uuid import uuid4

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import get_settings
from synaptiq.infrastructure.database import get_async_session
from synaptiq.services.auth_service import AuthError, AuthService
from synaptiq.workers.tasks import onboard_user_task

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


OAuthProvider = Literal["google", "github"]
OAuthMode = Literal["login", "signup"]


def _validate_oauth_provider(provider: str) -> OAuthProvider:
    """Validate provider path param and normalize casing."""
    normalized = provider.lower().strip()
    if normalized not in {"google", "github"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Unsupported OAuth provider",
                "code": "unsupported_provider",
            },
        )
    return normalized  # type: ignore[return-value]


def _normalize_origin(value: str) -> str:
    """Normalize origin strings for strict equality checks."""
    return value.rstrip("/")


def _resolve_frontend_origin(origin: Optional[str]) -> str:
    """
    Resolve and validate frontend origin for OAuth popup communication.

    We intentionally enforce a strict allowlist to prevent open redirects
    and postMessage target-origin abuse.
    """
    settings = get_settings()
    allowed_origin = _normalize_origin(settings.frontend_origin)
    requested_origin = _normalize_origin(origin) if origin else allowed_origin

    if requested_origin != allowed_origin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Invalid OAuth origin",
                "code": "invalid_oauth_origin",
            },
        )

    return requested_origin


def _oauth_provider_config(provider: OAuthProvider) -> dict[str, str]:
    """Get OAuth endpoint and credential configuration for a provider."""
    settings = get_settings()

    if provider == "google":
        return {
            "client_id": settings.google_oauth_client_id or "",
            "client_secret": settings.google_oauth_client_secret or "",
            "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
            "token_url": "https://oauth2.googleapis.com/token",
            "userinfo_url": "https://openidconnect.googleapis.com/v1/userinfo",
            "scope": "openid email profile",
        }

    if provider == "github":
        return {
            "client_id": settings.github_oauth_client_id or "",
            "client_secret": settings.github_oauth_client_secret or "",
            "authorize_url": "https://github.com/login/oauth/authorize",
            "token_url": "https://github.com/login/oauth/access_token",
            "userinfo_url": "https://api.github.com/user",
            "emails_url": "https://api.github.com/user/emails",
            "scope": "read:user user:email",
        }

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={"message": "Unsupported OAuth provider", "code": "unsupported_provider"},
    )


def _build_oauth_callback_url(request: Request, provider: OAuthProvider) -> str:
    """Build the OAuth callback URL, optionally using a public backend base URL."""
    settings = get_settings()
    callback_path = f"/api/v1/auth/oauth/{provider}/callback"

    if settings.oauth_backend_base_url:
        return f"{settings.oauth_backend_base_url.rstrip('/')}{callback_path}"

    return str(request.url_for("oauth_callback", provider=provider))


def _build_oauth_state(provider: OAuthProvider, mode: OAuthMode, origin: str) -> str:
    """Create a short-lived signed OAuth state token for CSRF protection."""
    settings = get_settings()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)

    payload = {
        "type": "oauth_state",
        "provider": provider,
        "mode": mode,
        "origin": origin,
        "nonce": str(uuid4()),
        "iat": datetime.now(timezone.utc),
        "exp": expires_at,
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def _decode_oauth_state(state_token: str, expected_provider: OAuthProvider) -> dict[str, Any]:
    """Validate and decode OAuth state token."""
    settings = get_settings()

    try:
        payload = jwt.decode(
            state_token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as exc:
        raise ValueError("invalid_state_token") from exc

    if payload.get("type") != "oauth_state":
        raise ValueError("invalid_state_type")
    if payload.get("provider") != expected_provider:
        raise ValueError("state_provider_mismatch")

    mode = payload.get("mode")
    if mode not in {"login", "signup"}:
        raise ValueError("invalid_state_mode")

    origin = payload.get("origin")
    if not origin or _normalize_origin(origin) != _normalize_origin(settings.frontend_origin):
        raise ValueError("invalid_state_origin")

    return payload


def _json_for_script(value: Any) -> str:
    """Serialize JSON safely for embedding in inline script blocks."""
    return json.dumps(value).replace("</", "<\\/")


def _oauth_popup_response(
    *,
    origin: str,
    fallback_path: str,
    payload: Optional[dict[str, Any]] = None,
    error: Optional[dict[str, str]] = None,
) -> HTMLResponse:
    """
    Return an HTML page for OAuth popup completion.

    The page posts a message to the opener window and closes itself.
    If no opener exists, it redirects to the frontend auth page.
    """
    message: dict[str, Any] = {
        "type": "synaptiq_oauth_result",
        "status": "error" if error else "success",
    }
    if payload:
        message["payload"] = payload
    if error:
        message["error"] = error

    html = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Synaptiq OAuth</title>
  </head>
  <body>
    <script>
      (function() {{
        var targetOrigin = {_json_for_script(origin)};
        var message = {_json_for_script(message)};

        try {{
          if (window.opener && !window.opener.closed) {{
            window.opener.postMessage(message, targetOrigin);
            window.close();
            return;
          }}
        }} catch (e) {{
          // Fall through to redirect.
        }}

        var redirectUrl = new URL({_json_for_script(fallback_path)}, targetOrigin);
        if (message.status === "error" && message.error && message.error.code) {{
          redirectUrl.searchParams.set("oauth_error", message.error.code);
        }} else {{
          redirectUrl.searchParams.set("oauth", "success");
        }}
        window.location.replace(redirectUrl.toString());
      }})();
    </script>
  </body>
</html>
"""

    return HTMLResponse(content=html)


def _oauth_fallback_path(mode: OAuthMode) -> str:
    """Map OAuth flow mode to the corresponding frontend page."""
    return "/signup" if mode == "signup" else "/login"


def _ensure_oauth_provider_configured(provider: OAuthProvider) -> dict[str, str]:
    """Ensure OAuth client credentials are configured."""
    config = _oauth_provider_config(provider)
    if not config.get("client_id") or not config.get("client_secret"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "message": f"{provider.title()} OAuth is not configured on the server",
                "code": "oauth_not_configured",
            },
        )
    return config


def _pick_verified_github_email(email_rows: list[dict[str, Any]]) -> Optional[str]:
    """Pick the best verified email from GitHub email rows."""
    verified_rows = [row for row in email_rows if row.get("verified")]
    if not verified_rows:
        return None

    primary_verified = next((row for row in verified_rows if row.get("primary")), None)
    selected = primary_verified or verified_rows[0]
    email = selected.get("email")
    return email.lower().strip() if isinstance(email, str) and email.strip() else None


async def _fetch_google_identity(
    *,
    code: str,
    redirect_uri: str,
    config: dict[str, str],
) -> dict[str, Optional[str]]:
    """Exchange Google code and return normalized identity profile."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        token_res = await client.post(
            config["token_url"],
            data={
                "code": code,
                "client_id": config["client_id"],
                "client_secret": config["client_secret"],
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        if token_res.status_code >= 400:
            raise AuthError("Google OAuth token exchange failed", code="oauth_token_exchange_failed")

        token_data = token_res.json()
        access_token = token_data.get("access_token")
        if not access_token:
            raise AuthError("Google OAuth did not return an access token", code="oauth_token_missing")

        profile_res = await client.get(
            config["userinfo_url"],
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if profile_res.status_code >= 400:
            raise AuthError("Failed to fetch Google user profile", code="oauth_profile_fetch_failed")

        profile = profile_res.json()

    email = profile.get("email")
    email_verified = bool(profile.get("email_verified"))
    oauth_id = profile.get("sub")

    if not email or not email_verified or not oauth_id:
        raise AuthError(
            "Google account must have a verified email address",
            code="oauth_email_not_verified",
        )

    return {
        "oauth_id": str(oauth_id),
        "email": str(email).lower().strip(),
        "name": profile.get("name"),
        "avatar_url": profile.get("picture"),
    }


async def _fetch_github_identity(
    *,
    code: str,
    redirect_uri: str,
    config: dict[str, str],
) -> dict[str, Optional[str]]:
    """Exchange GitHub code and return normalized identity profile."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        token_res = await client.post(
            config["token_url"],
            headers={"Accept": "application/json"},
            data={
                "code": code,
                "client_id": config["client_id"],
                "client_secret": config["client_secret"],
                "redirect_uri": redirect_uri,
            },
        )
        if token_res.status_code >= 400:
            raise AuthError("GitHub OAuth token exchange failed", code="oauth_token_exchange_failed")

        token_data = token_res.json()
        access_token = token_data.get("access_token")
        if not access_token:
            raise AuthError("GitHub OAuth did not return an access token", code="oauth_token_missing")

        base_headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        user_res = await client.get(config["userinfo_url"], headers=base_headers)
        if user_res.status_code >= 400:
            raise AuthError("Failed to fetch GitHub user profile", code="oauth_profile_fetch_failed")

        user_data = user_res.json()
        oauth_id = user_data.get("id")
        if oauth_id is None:
            raise AuthError("GitHub profile missing user identifier", code="oauth_profile_invalid")

        email = user_data.get("email")
        normalized_email: Optional[str] = None
        if isinstance(email, str) and email.strip():
            normalized_email = email.lower().strip()
        else:
            emails_res = await client.get(config["emails_url"], headers=base_headers)
            if emails_res.status_code >= 400:
                raise AuthError("Unable to fetch GitHub email addresses", code="oauth_profile_invalid")
            email_rows = emails_res.json()
            if not isinstance(email_rows, list):
                raise AuthError("Invalid GitHub email response", code="oauth_profile_invalid")
            normalized_email = _pick_verified_github_email(email_rows)

        if not normalized_email:
            raise AuthError(
                "GitHub account must have a verified email address",
                code="oauth_email_not_verified",
            )

        return {
            "oauth_id": str(oauth_id),
            "email": normalized_email,
            "name": user_data.get("name") or user_data.get("login"),
            "avatar_url": user_data.get("avatar_url"),
        }


async def _fetch_oauth_identity(
    *,
    provider: OAuthProvider,
    code: str,
    redirect_uri: str,
    config: dict[str, str],
) -> dict[str, Optional[str]]:
    """Fetch normalized OAuth identity profile for the given provider."""
    if provider == "google":
        return await _fetch_google_identity(code=code, redirect_uri=redirect_uri, config=config)
    return await _fetch_github_identity(code=code, redirect_uri=redirect_uri, config=config)


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
        
        # Trigger async graph provisioning for the new user
        onboard_user_task.delay(user.id)
        logger.info("Triggered graph provisioning", user_id=user.id)
        
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


@router.get(
    "/oauth/{provider}/start",
    summary="Start OAuth login/signup flow",
    responses={
        302: {"description": "Redirects to provider authorization page"},
        400: {"description": "Invalid provider or origin"},
        503: {"description": "OAuth provider not configured"},
    },
)
async def oauth_start(
    provider: str,
    request: Request,
    mode: OAuthMode = "login",
    origin: Optional[str] = None,
):
    """
    Start an OAuth flow with Google or GitHub.

    Returns a redirect response to the provider's authorization page.
    """
    provider_name = _validate_oauth_provider(provider)
    resolved_origin = _resolve_frontend_origin(origin)
    config = _ensure_oauth_provider_configured(provider_name)
    callback_url = _build_oauth_callback_url(request, provider_name)
    state_token = _build_oauth_state(provider_name, mode, resolved_origin)

    params: dict[str, str] = {
        "client_id": config["client_id"],
        "redirect_uri": callback_url,
        "response_type": "code",
        "scope": config["scope"],
        "state": state_token,
    }
    if provider_name == "google":
        params["access_type"] = "online"
        params["prompt"] = "select_account"
    else:
        params["allow_signup"] = "true"

    authorization_url = f"{config['authorize_url']}?{urlencode(params)}"
    return RedirectResponse(url=authorization_url, status_code=status.HTTP_302_FOUND)


@router.get(
    "/oauth/{provider}/callback",
    include_in_schema=False,
    name="oauth_callback",
)
async def oauth_callback(
    provider: str,
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    error_description: Optional[str] = None,
    session: AsyncSession = Depends(get_async_session),
):
    """
    OAuth callback handler for Google/GitHub popup flow.

    The response is an HTML page that posts auth data to the opener window.
    """
    provider_name = _validate_oauth_provider(provider)
    origin = _normalize_origin(get_settings().frontend_origin)
    mode: OAuthMode = "login"
    fallback_path = _oauth_fallback_path(mode)

    if not state:
        return _oauth_popup_response(
            origin=origin,
            fallback_path=fallback_path,
            error={"message": "Missing OAuth state", "code": "missing_oauth_state"},
        )

    try:
        state_payload = _decode_oauth_state(state, provider_name)
        origin = _normalize_origin(state_payload["origin"])
        mode = state_payload["mode"]
        fallback_path = _oauth_fallback_path(mode)
    except ValueError as exc:
        logger.warning(
            "OAuth callback rejected due to invalid state",
            provider=provider_name,
            error=str(exc),
        )
        return _oauth_popup_response(
            origin=origin,
            fallback_path=fallback_path,
            error={"message": "Invalid OAuth state", "code": "invalid_oauth_state"},
        )

    if error:
        logger.warning(
            "OAuth provider returned error",
            provider=provider_name,
            oauth_error=error,
            description=error_description,
        )
        return _oauth_popup_response(
            origin=origin,
            fallback_path=fallback_path,
            error={
                "message": error_description or "OAuth provider authentication failed",
                "code": "oauth_provider_error",
            },
        )

    if not code:
        return _oauth_popup_response(
            origin=origin,
            fallback_path=fallback_path,
            error={"message": "Missing OAuth authorization code", "code": "missing_oauth_code"},
        )

    try:
        config = _ensure_oauth_provider_configured(provider_name)
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        return _oauth_popup_response(
            origin=origin,
            fallback_path=fallback_path,
            error={
                "message": detail.get("message", "OAuth provider is not configured"),
                "code": detail.get("code", "oauth_not_configured"),
            },
        )

    callback_url = _build_oauth_callback_url(request, provider_name)
    try:
        identity = await _fetch_oauth_identity(
            provider=provider_name,
            code=code,
            redirect_uri=callback_url,
            config=config,
        )
    except AuthError as exc:
        logger.warning(
            "OAuth profile retrieval failed",
            provider=provider_name,
            error=exc.code,
        )
        return _oauth_popup_response(
            origin=origin,
            fallback_path=fallback_path,
            error={"message": exc.message, "code": exc.code},
        )
    except Exception:
        logger.exception("Unexpected OAuth profile retrieval error", provider=provider_name)
        return _oauth_popup_response(
            origin=origin,
            fallback_path=fallback_path,
            error={
                "message": "OAuth authentication failed unexpectedly",
                "code": "oauth_unexpected_error",
            },
        )

    user_agent, ip_address = get_client_info(request)
    auth_service = AuthService(session)

    try:
        user, token_pair, is_new_user = await auth_service.login_with_oauth(
            provider=provider_name,
            oauth_id=identity["oauth_id"] or "",
            email=identity["email"] or "",
            name=identity.get("name"),
            avatar_url=identity.get("avatar_url"),
            user_agent=user_agent,
            ip_address=ip_address,
        )
    except AuthError as exc:
        logger.warning(
            "OAuth login failed",
            provider=provider_name,
            error=exc.code,
        )
        return _oauth_popup_response(
            origin=origin,
            fallback_path=fallback_path,
            error={"message": exc.message, "code": exc.code},
        )

    if is_new_user:
        onboard_user_task.delay(user.id)
        logger.info("Triggered graph provisioning for OAuth user", user_id=user.id)

    auth_payload = {
        "user": user_to_response(user).model_dump(),
        "tokens": TokenResponse(**token_pair.to_dict()).model_dump(),
    }

    return _oauth_popup_response(
        origin=origin,
        fallback_path=fallback_path,
        payload=auth_payload,
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
