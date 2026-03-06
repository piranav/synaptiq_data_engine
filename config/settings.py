"""
Application configuration using Pydantic Settings.
Loads from environment variables with .env file support.
"""

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # SUPADATA
    supadata_api_key: str = Field(..., description="SUPADATA API key")

    # OpenAI
    openai_api_key: str = Field(..., description="OpenAI API key")

    # Anthropic (system-level fallback; users can also store their own key)
    anthropic_api_key: Optional[str] = Field(
        default=None,
        description="Anthropic API key (system fallback)",
    )

    # Qdrant
    qdrant_url: str = Field(..., description="Qdrant Cloud URL")
    qdrant_api_key: str = Field(..., description="Qdrant API key")
    qdrant_collection_name: str = Field(
        default="personal_knowledge", description="Qdrant collection name"
    )

    # MongoDB
    mongodb_uri: str = Field(..., description="MongoDB connection URI")
    mongodb_database: str = Field(default="synaptiq", description="MongoDB database name")

    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0", description="Redis URL")

    # Apache Fuseki (RDF Graph Store)
    fuseki_url: str = Field(
        default="http://localhost:3030", description="Apache Fuseki SPARQL endpoint URL"
    )
    fuseki_dataset: str = Field(
        default="synaptiq", description="Fuseki dataset name"
    )
    fuseki_admin_user: str = Field(
        default="admin", description="Fuseki admin username"
    )
    fuseki_admin_password: str = Field(
        default="admin123", description="Fuseki admin password"
    )
    
    # Ontology Configuration
    ontology_base_uri: str = Field(
        default="https://synaptiq.ai/", description="Base URI for ontology namespaces"
    )

    # Embedding Configuration
    embedding_model: str = Field(
        default="text-embedding-3-small", description="OpenAI embedding model"
    )
    embedding_dimensions: int = Field(
        default=1536, description="Embedding vector dimensions"
    )

    # Chunking Configuration
    chunk_max_tokens: int = Field(
        default=500, description="Maximum tokens per chunk"
    )
    chunk_overlap_tokens: int = Field(
        default=50, description="Token overlap between chunks"
    )

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")

    # PostgreSQL (for Agent Sessions and Auth)
    postgres_url: str = Field(
        default="postgresql+asyncpg://synaptiq:synaptiq123@localhost:5433/synaptiq_agents",
        description="PostgreSQL URL for agent sessions and auth"
    )

    # JWT Configuration
    jwt_secret_key: str = Field(
        default="your-super-secret-key-change-in-production",
        description="Secret key for JWT encoding"
    )
    jwt_algorithm: str = Field(
        default="HS256",
        description="JWT encoding algorithm"
    )
    jwt_access_token_expire_minutes: int = Field(
        default=15,
        description="Access token expiration in minutes"
    )
    jwt_refresh_token_expire_days: int = Field(
        default=7,
        description="Refresh token expiration in days"
    )

    # Frontend / OAuth
    frontend_origin: str = Field(
        default="http://localhost:3000",
        description="Allowed frontend origin for OAuth popup communication"
    )
    oauth_backend_base_url: Optional[str] = Field(
        default=None,
        description="Public backend base URL for OAuth callback URLs"
    )
    google_oauth_client_id: Optional[str] = Field(
        default=None,
        description="Google OAuth client ID"
    )
    google_oauth_client_secret: Optional[str] = Field(
        default=None,
        description="Google OAuth client secret"
    )
    github_oauth_client_id: Optional[str] = Field(
        default=None,
        description="GitHub OAuth client ID"
    )
    github_oauth_client_secret: Optional[str] = Field(
        default=None,
        description="GitHub OAuth client secret"
    )

    # AWS S3 Configuration
    aws_access_key_id: Optional[str] = Field(
        default=None,
        description="AWS Access Key ID for S3"
    )
    aws_secret_access_key: Optional[str] = Field(
        default=None,
        description="AWS Secret Access Key for S3"
    )
    aws_region: str = Field(
        default="us-east-1",
        description="AWS Region for S3"
    )
    s3_bucket_name: str = Field(
        default="synaptiq-uploads",
        description="S3 bucket name for file uploads"
    )
    s3_endpoint_url: Optional[str] = Field(
        default=None,
        description="Custom S3 endpoint URL (for MinIO or LocalStack)"
    )
    
    @property
    def s3_enabled(self) -> bool:
        """Check if S3 is configured."""
        return bool(self.aws_access_key_id and self.aws_secret_access_key)


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    Uses lru_cache to ensure settings are only loaded once.
    """
    return Settings()

