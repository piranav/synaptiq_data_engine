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


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    Uses lru_cache to ensure settings are only loaded once.
    """
    return Settings()


