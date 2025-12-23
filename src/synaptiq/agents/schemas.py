"""
Pydantic schemas for agent structured outputs.
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class IntentType(str, Enum):
    """Query intent types for strategy selection."""
    
    DEFINITION = "DEFINITION"  # "What is X?", "Define X"
    EXPLORATION = "EXPLORATION"  # "What do I know about X?"
    RELATIONSHIP = "RELATIONSHIP"  # "How does X relate to Y?"
    SOURCE_RECALL = "SOURCE_RECALL"  # "What did I learn from [source]?"
    SEMANTIC_SEARCH = "SEMANTIC_SEARCH"  # "Find notes about..."
    GENERAL = "GENERAL"  # No personal knowledge signals


class IntentClassification(BaseModel):
    """Structured output from intent classifier agent."""
    
    intent: IntentType = Field(
        description="The classified intent type"
    )
    entities: list[str] = Field(
        default_factory=list,
        description="Key entities/concepts extracted from the query"
    )
    requires_personal_knowledge: bool = Field(
        default=True,
        description="Whether the query requires personal knowledge base"
    )
    temporal_scope: Optional[str] = Field(
        default=None,
        description="Time filter if mentioned (e.g., 'last week', 'yesterday')"
    )
    source_filter: Optional[str] = Field(
        default=None,
        description="Source filter if mentioned (e.g., 'from YouTube', 'from notes')"
    )
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Confidence score for the classification"
    )


class RetrievalStrategy(str, Enum):
    """Retrieval strategy based on intent."""
    
    GRAPH_FIRST = "GRAPH_FIRST"  # Try graph, fallback to vector
    GRAPH_ONLY = "GRAPH_ONLY"  # Graph only (relationships, sources)
    VECTOR_FIRST = "VECTOR_FIRST"  # Vector first, enrich with graph
    HYBRID = "HYBRID"  # Both in parallel
    LLM_ONLY = "LLM_ONLY"  # No retrieval needed


class Citation(BaseModel):
    """A citation reference for the response."""
    
    id: int = Field(description="Citation number [1], [2], etc.")
    title: str = Field(description="Source title")
    url: Optional[str] = Field(default=None, description="Source URL if available")
    source_type: str = Field(default="unknown", description="Type of source")
    timestamp: Optional[str] = Field(
        default=None,
        description="Timestamp for video/audio sources (e.g., '12:45')"
    )


class RetrievalMetadata(BaseModel):
    """Metadata about the retrieval process."""
    
    retrieval_source: str = Field(
        description="Primary source: 'graph', 'vector', or 'llm_knowledge'"
    )
    fallback_chain: list[str] = Field(
        default_factory=list,
        description="Sources attempted in order"
    )
    has_citations: bool = Field(
        default=False,
        description="Whether response has citations"
    )
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Overall confidence (decreases with fallback)"
    )


class QueryResponse(BaseModel):
    """Final response from the query agent."""
    
    answer: str = Field(description="The synthesized answer text")
    citations: list[Citation] = Field(
        default_factory=list,
        description="List of citations referenced in the answer"
    )
    concepts_referenced: list[str] = Field(
        default_factory=list,
        description="Concepts from user's knowledge graph used"
    )
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Overall confidence score"
    )
    source_type: str = Field(
        default="personal_knowledge",
        description="'personal_knowledge' or 'llm_knowledge'"
    )
    retrieval_metadata: Optional[RetrievalMetadata] = Field(
        default=None,
        description="Details about retrieval process"
    )


class VectorSearchResult(BaseModel):
    """Result from vector search tool."""
    
    chunk_id: str
    text: str
    score: float
    source_title: Optional[str] = None
    source_url: Optional[str] = None
    source_type: Optional[str] = None
    timestamp_start: Optional[int] = None


class GraphSearchResult(BaseModel):
    """Result from graph/SPARQL queries."""
    
    concept_uri: Optional[str] = None
    label: Optional[str] = None
    definition_text: Optional[str] = None
    source_title: Optional[str] = None
    source_url: Optional[str] = None
    relationships: list[dict] = Field(default_factory=list)


class SparqlQueryResult(BaseModel):
    """Structured SPARQL query result."""
    
    query: str = Field(description="The SPARQL query that was executed")
    results: list[dict] = Field(
        default_factory=list,
        description="Query result bindings"
    )
    success: bool = Field(default=True)
    error: Optional[str] = Field(default=None)
