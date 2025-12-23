"""
Chat API routes for conversational knowledge retrieval.

Provides endpoints for:
- Sending chat messages and receiving responses
- Streaming chat responses
- Managing conversation sessions
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse
import structlog

from synaptiq.agents import QueryAgent, get_session, QueryResponse
from synaptiq.agents.session import list_user_sessions, delete_session

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class ChatRequest(BaseModel):
    """Request body for chat endpoint."""
    
    query: str = Field(
        ...,
        description="The user's question or message",
        min_length=1,
        max_length=2000,
    )
    session_id: str = Field(
        ...,
        description="Conversation session ID for history tracking",
        min_length=1,
        max_length=100,
    )


class ChatResponse(BaseModel):
    """Response from chat endpoint."""
    
    answer: str = Field(description="The generated answer")
    citations: list[dict] = Field(
        default_factory=list,
        description="List of source citations"
    )
    concepts_referenced: list[str] = Field(
        default_factory=list,
        description="Concepts from knowledge graph used"
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score"
    )
    source_type: str = Field(
        description="'personal_knowledge' or 'llm_knowledge'"
    )
    retrieval_metadata: Optional[dict] = Field(
        default=None,
        description="Details about retrieval process"
    )


class SessionInfo(BaseModel):
    """Information about a chat session."""
    
    session_id: str
    message_count: int = 0


class SessionListResponse(BaseModel):
    """Response for session list endpoint."""
    
    sessions: list[str]
    user_id: str


# =============================================================================
# DEPENDENCY INJECTION
# =============================================================================

# Cached agent instance
_agent: Optional[QueryAgent] = None


async def get_query_agent() -> QueryAgent:
    """Get or create the QueryAgent instance."""
    global _agent
    
    if _agent is None:
        logger.info("Initializing QueryAgent")
        _agent = QueryAgent()
    
    return _agent


# =============================================================================
# CHAT ENDPOINTS
# =============================================================================

@router.post("/{user_id}", response_model=ChatResponse)
async def chat(
    user_id: str,
    request: ChatRequest,
    agent: QueryAgent = Depends(get_query_agent),
):
    """
    Send a chat message and get a response from the knowledge base.
    
    The agent will:
    1. Classify the intent of your query
    2. Search your knowledge graph and/or vector store
    3. Synthesize a response with citations
    
    Args:
        user_id: Your user identifier
        request: Chat request with query and session_id
        
    Returns:
        ChatResponse with answer, citations, and metadata
    """
    logger.info(
        "Chat request",
        user_id=user_id,
        session_id=request.session_id,
        query_length=len(request.query),
    )
    
    try:
        response = await agent.query(
            user_id=user_id,
            query=request.query,
            session_id=request.session_id,
        )
        
        return ChatResponse(
            answer=response.answer,
            citations=[c.model_dump() for c in response.citations],
            concepts_referenced=response.concepts_referenced,
            confidence=response.confidence,
            source_type=response.source_type,
            retrieval_metadata=response.retrieval_metadata.model_dump() 
                if response.retrieval_metadata else None,
        )
        
    except Exception as e:
        logger.error("Chat request failed", error=str(e), user_id=user_id)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process chat request: {str(e)}",
        )


@router.post("/{user_id}/stream")
async def chat_stream(
    user_id: str,
    request: ChatRequest,
    agent: QueryAgent = Depends(get_query_agent),
):
    """
    Send a chat message and stream the response.
    
    Returns a Server-Sent Events (SSE) stream with response chunks.
    
    Args:
        user_id: Your user identifier
        request: Chat request with query and session_id
        
    Returns:
        EventSourceResponse streaming the answer
    """
    logger.info(
        "Streaming chat request",
        user_id=user_id,
        session_id=request.session_id,
    )
    
    async def event_generator():
        """Generate SSE events from streaming response."""
        try:
            async for chunk in agent.query_stream(
                user_id=user_id,
                query=request.query,
                session_id=request.session_id,
            ):
                yield {
                    "event": "message",
                    "data": chunk,
                }
            
            # Send completion event
            yield {
                "event": "done",
                "data": "",
            }
            
        except Exception as e:
            logger.error("Streaming failed", error=str(e))
            yield {
                "event": "error",
                "data": str(e),
            }
    
    return EventSourceResponse(event_generator())


# =============================================================================
# SESSION MANAGEMENT ENDPOINTS
# =============================================================================

@router.get("/{user_id}/sessions", response_model=SessionListResponse)
async def get_sessions(user_id: str):
    """
    List all conversation sessions for a user.
    
    Args:
        user_id: User identifier
        
    Returns:
        List of session IDs
    """
    try:
        sessions = await list_user_sessions(user_id)
        
        return SessionListResponse(
            sessions=sessions,
            user_id=user_id,
        )
        
    except Exception as e:
        logger.error("Failed to list sessions", error=str(e), user_id=user_id)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list sessions: {str(e)}",
        )


@router.get("/{user_id}/sessions/{session_id}/history")
async def get_chat_history(user_id: str, session_id: str):
    """
    Get conversation history for a session.
    
    Args:
        user_id: User identifier
        session_id: Session identifier
        
    Returns:
        Conversation history as list of messages
    """
    try:
        session = await get_session(session_id, user_id)
        
        # Get items from session
        items = await session.get_items()
        
        # Format history
        history = []
        for item in items:
            if hasattr(item, 'role') and hasattr(item, 'content'):
                history.append({
                    "role": item.role,
                    "content": item.content if isinstance(item.content, str) 
                              else str(item.content),
                })
        
        return {
            "session_id": session_id,
            "user_id": user_id,
            "history": history,
            "message_count": len(history),
        }
        
    except Exception as e:
        logger.error(
            "Failed to get chat history",
            error=str(e),
            user_id=user_id,
            session_id=session_id,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get chat history: {str(e)}",
        )


@router.delete("/{user_id}/sessions/{session_id}")
async def clear_session(user_id: str, session_id: str):
    """
    Delete a conversation session.
    
    This permanently removes all messages in the session.
    
    Args:
        user_id: User identifier
        session_id: Session identifier
        
    Returns:
        Status of deletion
    """
    try:
        deleted = await delete_session(session_id, user_id)
        
        return {
            "session_id": session_id,
            "user_id": user_id,
            "deleted": deleted,
            "status": "deleted" if deleted else "not_found",
        }
        
    except Exception as e:
        logger.error(
            "Failed to delete session",
            error=str(e),
            user_id=user_id,
            session_id=session_id,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete session: {str(e)}",
        )


# =============================================================================
# HEALTH/STATUS ENDPOINTS
# =============================================================================

@router.get("/health")
async def health_check():
    """Check if the chat service is healthy."""
    return {
        "status": "healthy",
        "service": "chat",
    }
