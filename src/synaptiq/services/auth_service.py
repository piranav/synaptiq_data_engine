"""
Authentication service for user registration, login, and token management.

Handles:
- User registration with email/password
- Login and JWT token generation
- Token refresh flow
- Password hashing and verification
- Session management
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from uuid import uuid4

import bcrypt
import structlog
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import get_settings
from synaptiq.domain.models import Session, User, UserSettings

logger = structlog.get_logger(__name__)


class TokenPair:
    """Access and refresh token pair."""
    
    def __init__(self, access_token: str, refresh_token: str, token_type: str = "bearer"):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.token_type = token_type
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "token_type": self.token_type,
        }


class AuthError(Exception):
    """Authentication error."""
    
    def __init__(self, message: str, code: str = "auth_error"):
        self.message = message
        self.code = code
        super().__init__(message)


class AuthService:
    """
    Authentication service for managing user auth flows.
    
    Provides methods for:
    - signup: Create new user with email/password
    - login: Authenticate and generate tokens
    - refresh_token: Get new access token using refresh token
    - logout: Invalidate session
    - verify_token: Validate and decode access token
    """
    
    def __init__(self, session: AsyncSession):
        """
        Initialize auth service with database session.
        
        Args:
            session: SQLAlchemy async session
        """
        self.session = session
        self.settings = get_settings()
    
    # =========================================================================
    # Password Utilities
    # =========================================================================
    
    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash a password using bcrypt.
        
        Args:
            password: Plain text password
            
        Returns:
            Hashed password
        """
        password_bytes = password.encode('utf-8')
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password_bytes, salt).decode('utf-8')
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """
        Verify a password against its hash.
        
        Args:
            plain_password: Plain text password to verify
            hashed_password: Stored password hash
            
        Returns:
            True if password matches
        """
        try:
            password_bytes = plain_password.encode('utf-8')
            hash_bytes = hashed_password.encode('utf-8')
            return bcrypt.checkpw(password_bytes, hash_bytes)
        except Exception:
            return False
    
    # =========================================================================
    # Token Utilities
    # =========================================================================
    
    def create_access_token(self, user_id: str) -> str:
        """
        Create a short-lived access token.
        
        Args:
            user_id: User ID to encode in token
            
        Returns:
            JWT access token
        """
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=self.settings.jwt_access_token_expire_minutes
        )
        
        payload = {
            "sub": user_id,
            "exp": expire,
            "iat": datetime.now(timezone.utc),
            "type": "access",
        }
        
        return jwt.encode(
            payload,
            self.settings.jwt_secret_key,
            algorithm=self.settings.jwt_algorithm,
        )
    
    def create_refresh_token(self, user_id: str) -> Tuple[str, datetime]:
        """
        Create a long-lived refresh token.
        
        Args:
            user_id: User ID to encode in token
            
        Returns:
            Tuple of (JWT refresh token, expiration datetime)
        """
        expire = datetime.now(timezone.utc) + timedelta(
            days=self.settings.jwt_refresh_token_expire_days
        )
        
        payload = {
            "sub": user_id,
            "exp": expire,
            "iat": datetime.now(timezone.utc),
            "type": "refresh",
            "jti": str(uuid4()),  # Unique token ID
        }
        
        token = jwt.encode(
            payload,
            self.settings.jwt_secret_key,
            algorithm=self.settings.jwt_algorithm,
        )
        
        return token, expire
    
    def decode_token(self, token: str) -> Optional[dict]:
        """
        Decode and validate a JWT token.
        
        Args:
            token: JWT token to decode
            
        Returns:
            Decoded payload or None if invalid
        """
        try:
            payload = jwt.decode(
                token,
                self.settings.jwt_secret_key,
                algorithms=[self.settings.jwt_algorithm],
            )
            return payload
        except JWTError as e:
            logger.warning("Token decode failed", error=str(e))
            return None
    
    async def _create_token_pair(
        self,
        user: User,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> TokenPair:
        """
        Create access and refresh token pair for a user.
        
        Also creates a session record in the database.
        
        Args:
            user: User to create tokens for
            user_agent: Optional user agent string
            ip_address: Optional IP address
            
        Returns:
            TokenPair with access and refresh tokens
        """
        access_token = self.create_access_token(user.id)
        refresh_token, expires_at = self.create_refresh_token(user.id)
        
        # Create session record
        session = Session(
            user_id=user.id,
            refresh_token=refresh_token,
            expires_at=expires_at,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        self.session.add(session)
        
        return TokenPair(access_token, refresh_token)
    
    # =========================================================================
    # User Operations
    # =========================================================================
    
    async def get_user_by_email(self, email: str) -> Optional[User]:
        """
        Get a user by email address.
        
        Args:
            email: Email address to search for
            
        Returns:
            User if found, None otherwise
        """
        result = await self.session.execute(
            select(User).where(User.email == email.lower())
        )
        return result.scalar_one_or_none()
    
    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        """
        Get a user by ID.
        
        Args:
            user_id: User ID to search for
            
        Returns:
            User if found, None otherwise
        """
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()
    
    # =========================================================================
    # Auth Flows
    # =========================================================================
    
    async def signup(
        self,
        email: str,
        password: str,
        name: Optional[str] = None,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> Tuple[User, TokenPair]:
        """
        Register a new user with email and password.
        
        Args:
            email: User's email address
            password: Plain text password (min 8 chars)
            name: Optional display name
            user_agent: Optional user agent string
            ip_address: Optional IP address
            
        Returns:
            Tuple of (created User, TokenPair)
            
        Raises:
            AuthError: If email already exists or validation fails
        """
        email = email.lower().strip()
        
        # Validate password length
        if len(password) < 8:
            raise AuthError(
                "Password must be at least 8 characters",
                code="password_too_short",
            )
        
        # Check if email already exists
        existing = await self.get_user_by_email(email)
        if existing:
            raise AuthError(
                "An account with this email already exists",
                code="email_exists",
            )
        
        # Create user
        user = User(
            email=email,
            password_hash=self.hash_password(password),
            name=name,
        )
        self.session.add(user)
        
        # Flush to get user ID before creating related objects
        await self.session.flush()
        
        # Create default settings (now user.id is available)
        settings = UserSettings(user_id=user.id)
        self.session.add(settings)
        
        # Create tokens
        token_pair = await self._create_token_pair(user, user_agent, ip_address)
        
        logger.info("User signed up", user_id=user.id, email=email)
        
        return user, token_pair
    
    async def login(
        self,
        email: str,
        password: str,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> Tuple[User, TokenPair]:
        """
        Authenticate user with email and password.
        
        Args:
            email: User's email address
            password: Plain text password
            user_agent: Optional user agent string
            ip_address: Optional IP address
            
        Returns:
            Tuple of (User, TokenPair)
            
        Raises:
            AuthError: If credentials are invalid
        """
        email = email.lower().strip()
        
        # Find user
        user = await self.get_user_by_email(email)
        if not user:
            raise AuthError(
                "Invalid email or password",
                code="invalid_credentials",
            )
        
        # Check if user has a password (not OAuth-only)
        if not user.password_hash:
            raise AuthError(
                "This account uses social login. Please sign in with Google or GitHub.",
                code="oauth_only_account",
            )
        
        # Verify password
        if not self.verify_password(password, user.password_hash):
            raise AuthError(
                "Invalid email or password",
                code="invalid_credentials",
            )
        
        # Check if user is active
        if not user.is_active:
            raise AuthError(
                "This account has been deactivated",
                code="account_deactivated",
            )
        
        # Create tokens
        token_pair = await self._create_token_pair(user, user_agent, ip_address)
        
        logger.info("User logged in", user_id=user.id, email=email)
        
        return user, token_pair
    
    async def refresh_token(
        self,
        refresh_token: str,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> TokenPair:
        """
        Generate new token pair using a refresh token.
        
        The old refresh token is invalidated and a new one is created.
        
        Args:
            refresh_token: Current refresh token
            user_agent: Optional user agent string
            ip_address: Optional IP address
            
        Returns:
            New TokenPair
            
        Raises:
            AuthError: If refresh token is invalid or expired
        """
        # Decode and validate token
        payload = self.decode_token(refresh_token)
        if not payload:
            raise AuthError(
                "Invalid refresh token",
                code="invalid_token",
            )
        
        if payload.get("type") != "refresh":
            raise AuthError(
                "Invalid token type",
                code="invalid_token_type",
            )
        
        user_id = payload.get("sub")
        if not user_id:
            raise AuthError(
                "Invalid token payload",
                code="invalid_token",
            )
        
        # Find and validate session
        result = await self.session.execute(
            select(Session).where(Session.refresh_token == refresh_token)
        )
        db_session = result.scalar_one_or_none()
        
        if not db_session:
            raise AuthError(
                "Session not found",
                code="session_not_found",
            )
        
        if db_session.is_expired:
            # Delete expired session
            await self.session.delete(db_session)
            raise AuthError(
                "Refresh token has expired",
                code="token_expired",
            )
        
        # Get user
        user = await self.get_user_by_id(user_id)
        if not user or not user.is_active:
            await self.session.delete(db_session)
            raise AuthError(
                "User not found or inactive",
                code="user_not_found",
            )
        
        # Delete old session
        await self.session.delete(db_session)
        
        # Create new token pair
        token_pair = await self._create_token_pair(user, user_agent, ip_address)
        
        logger.info("Token refreshed", user_id=user.id)
        
        return token_pair
    
    async def logout(self, refresh_token: str) -> bool:
        """
        Invalidate a session by deleting its refresh token.
        
        Args:
            refresh_token: Refresh token to invalidate
            
        Returns:
            True if session was found and deleted
        """
        result = await self.session.execute(
            select(Session).where(Session.refresh_token == refresh_token)
        )
        db_session = result.scalar_one_or_none()
        
        if db_session:
            await self.session.delete(db_session)
            logger.info("User logged out", user_id=db_session.user_id)
            return True
        
        return False
    
    async def logout_all(self, user_id: str) -> int:
        """
        Invalidate all sessions for a user.
        
        Args:
            user_id: User ID to logout from all devices
            
        Returns:
            Number of sessions deleted
        """
        result = await self.session.execute(
            select(Session).where(Session.user_id == user_id)
        )
        sessions = result.scalars().all()
        
        count = len(sessions)
        for session in sessions:
            await self.session.delete(session)
        
        logger.info("User logged out from all devices", user_id=user_id, sessions=count)
        
        return count
    
    async def verify_access_token(self, token: str) -> Optional[User]:
        """
        Verify an access token and return the associated user.
        
        Args:
            token: JWT access token
            
        Returns:
            User if token is valid, None otherwise
        """
        payload = self.decode_token(token)
        if not payload:
            return None
        
        if payload.get("type") != "access":
            return None
        
        user_id = payload.get("sub")
        if not user_id:
            return None
        
        user = await self.get_user_by_id(user_id)
        if not user or not user.is_active:
            return None
        
        return user
    
    # =========================================================================
    # Password Reset
    # =========================================================================
    
    async def initiate_password_reset(self, email: str) -> Optional[str]:
        """
        Initiate password reset flow.
        
        Args:
            email: User's email address
            
        Returns:
            Reset token if user exists, None otherwise
            
        Note:
            In production, this would send an email rather than
            returning the token directly.
        """
        email = email.lower().strip()
        user = await self.get_user_by_email(email)
        
        if not user:
            # Don't reveal if email exists
            return None
        
        # Create reset token (valid for 1 hour)
        expire = datetime.now(timezone.utc) + timedelta(hours=1)
        payload = {
            "sub": user.id,
            "exp": expire,
            "type": "reset",
        }
        
        reset_token = jwt.encode(
            payload,
            self.settings.jwt_secret_key,
            algorithm=self.settings.jwt_algorithm,
        )
        
        logger.info("Password reset initiated", user_id=user.id)
        
        # In production, send email with reset link
        # For now, return token directly
        return reset_token
    
    async def reset_password(self, reset_token: str, new_password: str) -> bool:
        """
        Complete password reset with new password.
        
        Args:
            reset_token: Password reset token
            new_password: New password to set
            
        Returns:
            True if password was reset
            
        Raises:
            AuthError: If token is invalid or expired
        """
        if len(new_password) < 8:
            raise AuthError(
                "Password must be at least 8 characters",
                code="password_too_short",
            )
        
        payload = self.decode_token(reset_token)
        if not payload:
            raise AuthError(
                "Invalid or expired reset token",
                code="invalid_token",
            )
        
        if payload.get("type") != "reset":
            raise AuthError(
                "Invalid token type",
                code="invalid_token_type",
            )
        
        user_id = payload.get("sub")
        user = await self.get_user_by_id(user_id)
        
        if not user:
            raise AuthError(
                "User not found",
                code="user_not_found",
            )
        
        # Update password
        user.password_hash = self.hash_password(new_password)
        
        # Logout from all devices
        await self.logout_all(user_id)
        
        logger.info("Password reset completed", user_id=user.id)
        
        return True

