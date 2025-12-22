"""
FastAPI application factory and configuration.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config.settings import get_settings
from synaptiq.api.dependencies import cleanup_resources
from synaptiq.api.routes import ingest, jobs, search, sources
from synaptiq.core.exceptions import SynaptiqError

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Application lifespan manager."""
    # Startup
    logger.info("Starting Synaptiq Data Engine API")
    settings = get_settings()
    logger.info("Configuration loaded", log_level=settings.log_level)
    
    yield
    
    # Shutdown
    logger.info("Shutting down Synaptiq Data Engine API")
    await cleanup_resources()


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
        
        - **Ingest** content from YouTube videos and web articles
        - **Process** with semantic chunking and embeddings
        - **Search** your knowledge base with vector similarity
        - **Cite** sources with timestamps and URLs
        
        ## Quick Start
        
        1. **Ingest a YouTube video:**
           ```
           POST /ingest
           {"url": "https://youtube.com/watch?v=...", "user_id": "your_id"}
           ```
        
        2. **Check job status:**
           ```
           GET /jobs/{job_id}
           ```
        
        3. **Search your knowledge:**
           ```
           POST /search
           {"query": "What is a tensor?", "user_id": "your_id"}
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
    app.include_router(ingest.router)
    app.include_router(search.router)
    app.include_router(jobs.router)
    app.include_router(sources.router)

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

    return app


# Create app instance for uvicorn
app = create_app()


