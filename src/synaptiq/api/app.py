"""
FastAPI application factory and configuration.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

import structlog
from fastapi import FastAPI, Query, Request, WebSocket, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config.settings import get_settings
from synaptiq.api.dependencies import cleanup_resources
from synaptiq.api.routes import auth, ingest, jobs, notes, search, sources, chat, user, graph
from synaptiq.api.middleware.auth import AuthMiddleware
from synaptiq.api.websocket import manager as ws_manager, websocket_endpoint
from synaptiq.core.exceptions import SynaptiqError
from synaptiq.infrastructure.database import close_db

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Application lifespan manager."""
    # Startup
    logger.info("Starting Synaptiq Data Engine API")
    settings = get_settings()
    logger.info("Configuration loaded", log_level=settings.log_level)
    
    # Start WebSocket pub/sub listener
    await ws_manager.start_pubsub_listener()
    logger.info("WebSocket pub/sub listener started")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Synaptiq Data Engine API")
    
    # Stop WebSocket pub/sub listener
    await ws_manager.stop_pubsub_listener()
    logger.info("WebSocket pub/sub listener stopped")
    
    await cleanup_resources()
    await close_db()


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.
    
    Returns:
        Configured FastAPI application
    """
    settings = get_settings()

    app = FastAPI(
        title="Synaptiq Data Engine",
        description="""
        A production-grade data processing pipeline for personal knowledge management.
        
        ## Features
        
        - **Authentication** with JWT access/refresh tokens
        - **Ingest** content from YouTube videos and web articles
        - **Process** with semantic chunking and embeddings
        - **Search** your knowledge base with vector similarity
        - **Chat** with your knowledge using AI agents
        - **Cite** sources with timestamps and URLs
        
        ## Quick Start
        
        1. **Create an account:**
           ```
           POST /api/v1/auth/signup
           {"email": "you@example.com", "password": "yourpassword", "name": "Your Name"}
           ```
        
        2. **Login to get tokens:**
           ```
           POST /api/v1/auth/login
           {"email": "you@example.com", "password": "yourpassword"}
           ```
        
        3. **Ingest a YouTube video (with JWT):**
           ```
           POST /ingest
           Authorization: Bearer <access_token>
           {"url": "https://youtube.com/watch?v=..."}
           ```
        
        4. **Chat with your knowledge (with JWT):**
           ```
           POST /chat
           Authorization: Bearer <access_token>
           {"query": "What is a tensor?", "session_id": "my-session"}
           ```
        
        5. **Search your knowledge (with JWT):**
           ```
           POST /search
           Authorization: Bearer <access_token>
           {"query": "What is a tensor?"}
           ```
        """,
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Auth middleware - validates JWT and attaches user to request
    app.add_middleware(AuthMiddleware)

    # Exception handlers
    @app.exception_handler(SynaptiqError)
    async def synaptiq_error_handler(
        request: Request,
        exc: SynaptiqError,
    ) -> JSONResponse:
        """Handle Synaptiq-specific errors."""
        logger.error(
            "SynaptiqError",
            error_type=type(exc).__name__,
            message=exc.message,
            details=exc.details,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": type(exc).__name__,
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        """Handle unexpected errors."""
        logger.error(
            "Unhandled exception",
            error_type=type(exc).__name__,
            message=str(exc),
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "InternalServerError",
                "message": "An unexpected error occurred",
            },
        )

    # Include routers
    app.include_router(auth.router)
    app.include_router(user.router)
    app.include_router(ingest.router)
    app.include_router(search.router)
    app.include_router(jobs.router)
    app.include_router(sources.router)
    app.include_router(chat.router)
    app.include_router(graph.router)
    app.include_router(notes.router)

    # Health check endpoint
    @app.get("/health", tags=["Health"])
    async def health_check() -> dict:
        """Health check endpoint."""
        return {"status": "healthy", "version": "0.1.0"}

    # Root endpoint
    @app.get("/", tags=["Root"])
    async def root() -> dict:
        """Root endpoint with API info."""
        return {
            "name": "Synaptiq Data Engine",
            "version": "0.1.0",
            "docs": "/docs",
            "health": "/health",
        }
    
    # WebSocket endpoint
    @app.websocket("/ws")
    async def websocket_route(
        websocket: WebSocket,
        token: Optional[str] = Query(None, description="JWT access token"),
    ):
        """
        WebSocket endpoint for real-time updates.
        
        Connect with JWT token as query parameter: ws://host/ws?token=<jwt>
        Or send auth message after connecting: {"token": "<jwt>"}
        
        Events received:
        - job.started: Job has started processing
        - job.progress: Job progress update
        - job.completed: Job completed successfully
        - job.failed: Job failed
        - chat.token: Streaming chat response token
        - graph.updated: Knowledge graph updated
        """
        await websocket_endpoint(websocket, token)
    
    # WebSocket status endpoint
    @app.get("/ws/status", tags=["WebSocket"])
    async def websocket_status() -> dict:
        """Get WebSocket connection statistics."""
        return {
            "active_connections": ws_manager.get_connection_count(),
            "connected_users": ws_manager.get_user_count(),
        }

    return app


# Create app instance for uvicorn
app = create_app()


