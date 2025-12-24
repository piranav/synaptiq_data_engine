#!/usr/bin/env python
"""
Quick test script for authentication system.
Creates tables directly (no migrations needed) and tests the auth flow.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

async def main():
    print("=" * 60)
    print("SYNAPTIQ AUTH SYSTEM TEST")
    print("=" * 60)
    
    # Step 1: Initialize database tables
    print("\n[1/5] Initializing database tables...")
    try:
        from synaptiq.infrastructure.database import init_db, get_session_factory
        await init_db()
        print("✓ Database tables created successfully!")
    except Exception as e:
        print(f"✗ Failed to create tables: {e}")
        print("\nMake sure PostgreSQL is running:")
        print("  docker-compose up -d postgres")
        return
    
    # Step 2: Test signup
    print("\n[2/5] Testing signup...")
    try:
        from synaptiq.services.auth_service import AuthService
        
        session_factory = get_session_factory()
        async with session_factory() as session:
            auth_service = AuthService(session)
            
            user, tokens = await auth_service.signup(
                email="test@example.com",
                password="testpassword123",
                name="Test User",
            )
            await session.commit()
            
            print(f"✓ User created: {user.email} (ID: {user.id})")
            print(f"  Access token: {tokens.access_token[:50]}...")
            print(f"  Refresh token: {tokens.refresh_token[:50]}...")
            
            user_id = user.id
            access_token = tokens.access_token
            refresh_token = tokens.refresh_token
            
    except Exception as e:
        if "already exists" in str(e):
            print("! User already exists, trying login instead...")
        else:
            print(f"✗ Signup failed: {e}")
            return
    
    # Step 3: Test login
    print("\n[3/5] Testing login...")
    try:
        async with session_factory() as session:
            auth_service = AuthService(session)
            
            user, tokens = await auth_service.login(
                email="test@example.com",
                password="testpassword123",
            )
            await session.commit()
            
            print(f"✓ Login successful for: {user.email}")
            print(f"  User ID: {user.id}")
            
            user_id = user.id
            access_token = tokens.access_token
            refresh_token = tokens.refresh_token
            
    except Exception as e:
        print(f"✗ Login failed: {e}")
        return
    
    # Step 4: Test token verification
    print("\n[4/5] Testing token verification...")
    try:
        async with session_factory() as session:
            auth_service = AuthService(session)
            
            verified_user = await auth_service.verify_access_token(access_token)
            
            if verified_user:
                print(f"✓ Token verified for user: {verified_user.email}")
            else:
                print("✗ Token verification failed!")
                return
                
    except Exception as e:
        print(f"✗ Token verification error: {e}")
        return
    
    # Step 5: Test token refresh
    print("\n[5/5] Testing token refresh...")
    try:
        async with session_factory() as session:
            auth_service = AuthService(session)
            
            new_tokens = await auth_service.refresh_token(refresh_token)
            await session.commit()
            
            print(f"✓ Token refreshed successfully!")
            print(f"  New access token: {new_tokens.access_token[:50]}...")
            
    except Exception as e:
        print(f"✗ Token refresh failed: {e}")
        return
    
    print("\n" + "=" * 60)
    print("ALL TESTS PASSED!")
    print("=" * 60)
    
    print("\nYou can now start the API server with:")
    print("  uvicorn synaptiq.api.app:app --reload")
    print("\nThen test the endpoints at:")
    print("  http://localhost:8000/docs")
    print("\nAuth endpoints:")
    print("  POST /api/v1/auth/signup")
    print("  POST /api/v1/auth/login")
    print("  POST /api/v1/auth/refresh")
    print("  GET  /api/v1/auth/me (requires Bearer token)")


if __name__ == "__main__":
    asyncio.run(main())

