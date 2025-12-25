"""
Chat API routes for conversational knowledge retrieval.

Provides endpoints for:
- Sending chat messages and receiving responses
- Streaming chat responses
- Managing conversation sessions

Supports both authenticated (JWT) and legacy (user_id path param) modes.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse
import structlog

from synaptiq.agents import QueryAgent, get_session, QueryResponse
from synaptiq.agents.session import list_user_sessions, delete_session
from synaptiq.api.middleware.auth import get_current_user, get_current_user_optional
from synaptiq.domain.models import User

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


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
# AUTHENTICATED CHAT ENDPOINTS (New - JWT required)
# =============================================================================

@router.post("", response_model=ChatResponse)
async def chat_authenticated(
    request: ChatRequest,
    user: User = Depends(get_current_user),
    agent: QueryAgent = Depends(get_query_agent),
):
    """
    Send a chat message and get a response from the knowledge base.
    
    Requires JWT authentication.
    
    The agent will:
    1. Classify the intent of your query
    2. Search your knowledge graph and/or vector store
    3. Synthesize a response with citations
    
    Returns:
        ChatResponse with answer, citations, and metadata
    """
    logger.info(
        "Chat request (authenticated)",
        user_id=user.id,
        session_id=request.session_id,
        query_length=len(request.query),
    )
    
    try:
        response = await agent.query(
            user_id=user.id,
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
        logger.error("Chat request failed", error=str(e), user_id=user.id)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process chat request: {str(e)}",
        )


@router.post("/stream")
async def chat_stream_authenticated(
    request: ChatRequest,
    user: User = Depends(get_current_user),
    agent: QueryAgent = Depends(get_query_agent),
):
    """
    Send a chat message and stream the response.
    
    Requires JWT authentication.
    Returns a Server-Sent Events (SSE) stream with response chunks.
    """
    logger.info(
        "Streaming chat request (authenticated)",
        user_id=user.id,
        session_id=request.session_id,
    )
    
    user_id = user.id
    
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


@router.get("/sessions", response_model=SessionListResponse)
async def get_sessions_authenticated(
    user: User = Depends(get_current_user),
):
    """
    List all conversation sessions for the authenticated user.
    
    Requires JWT authentication.
    """
    try:
        sessions = await list_user_sessions(user.id)
        
        return SessionListResponse(
            sessions=sessions,
            user_id=user.id,
        )
        
    except Exception as e:
        logger.error("Failed to list sessions", error=str(e), user_id=user.id)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list sessions: {str(e)}",
        )


@router.get("/sessions/{session_id}/history")
async def get_chat_history_authenticated(
    session_id: str,
    user: User = Depends(get_current_user),
):
    """
    Get conversation history for a session.
    
    Requires JWT authentication.
    """
    try:
        session = await get_session(session_id, user.id)
        
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
            "user_id": user.id,
            "history": history,
            "message_count": len(history),
        }
        
    except Exception as e:
        logger.error(
            "Failed to get chat history",
            error=str(e),
            user_id=user.id,
            session_id=session_id,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get chat history: {str(e)}",
        )


@router.delete("/sessions/{session_id}")
async def clear_session_authenticated(
    session_id: str,
    user: User = Depends(get_current_user),
):
    """
    Delete a conversation session.
    
    Requires JWT authentication.
    This permanently removes all messages in the session.
    """
    try:
        deleted = await delete_session(session_id, user.id)
        
        return {
            "session_id": session_id,
            "user_id": user.id,
            "deleted": deleted,
            "status": "deleted" if deleted else "not_found",
        }
        
    except Exception as e:
        logger.error(
            "Failed to delete session",
            error=str(e),
            user_id=user.id,
            session_id=session_id,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete session: {str(e)}",
        )


# =============================================================================
# LEGACY CHAT ENDPOINTS (Deprecated - user_id in path)
# =============================================================================

@router.post(
    "/legacy/{user_id}",
    response_model=ChatResponse,
    deprecated=True,
    summary="[DEPRECATED] Send chat message",
    description="Deprecated: Use POST /chat with JWT authentication instead.",
)
async def chat_legacy(
    user_id: str,
    request: ChatRequest,
    agent: QueryAgent = Depends(get_query_agent),
):
    """
    [DEPRECATED] Send a chat message using user_id path parameter.
    
    Please migrate to POST /chat with JWT authentication.
    """
    logger.info(
        "Chat request (legacy)",
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


@router.post(
    "/legacy/{user_id}/stream",
    deprecated=True,
    summary="[DEPRECATED] Stream chat response",
    description="Deprecated: Use POST /chat/stream with JWT authentication instead.",
)
async def chat_stream_legacy(
    user_id: str,
    request: ChatRequest,
    agent: QueryAgent = Depends(get_query_agent),
):
    """
    [DEPRECATED] Stream chat response using user_id path parameter.
    
    Please migrate to POST /chat/stream with JWT authentication.
    """
    logger.info(
        "Streaming chat request (legacy)",
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


@router.get(
    "/legacy/{user_id}/sessions",
    response_model=SessionListResponse,
    deprecated=True,
    summary="[DEPRECATED] List sessions",
    description="Deprecated: Use GET /chat/sessions with JWT authentication instead.",
)
async def get_sessions_legacy(user_id: str):
    """[DEPRECATED] List sessions using user_id path parameter."""
    try:
        sessions = await list_user_sessions(user_id)
        return SessionListResponse(sessions=sessions, user_id=user_id)
    except Exception as e:
        logger.error("Failed to list sessions", error=str(e), user_id=user_id)
        raise HTTPException(status_code=500, detail=f"Failed to list sessions: {str(e)}")


@router.get(
    "/legacy/{user_id}/sessions/{session_id}/history",
    deprecated=True,
    summary="[DEPRECATED] Get chat history",
    description="Deprecated: Use GET /chat/sessions/{session_id}/history with JWT authentication instead.",
)
async def get_chat_history_legacy(user_id: str, session_id: str):
    """[DEPRECATED] Get chat history using user_id path parameter."""
    try:
        session = await get_session(session_id, user_id)
        items = await session.get_items()
        history = []
        for item in items:
            if hasattr(item, 'role') and hasattr(item, 'content'):
                history.append({
                    "role": item.role,
                    "content": item.content if isinstance(item.content, str) else str(item.content),
                })
        return {"session_id": session_id, "user_id": user_id, "history": history, "message_count": len(history)}
    except Exception as e:
        logger.error("Failed to get chat history", error=str(e), user_id=user_id, session_id=session_id)
        raise HTTPException(status_code=500, detail=f"Failed to get chat history: {str(e)}")


@router.delete(
    "/legacy/{user_id}/sessions/{session_id}",
    deprecated=True,
    summary="[DEPRECATED] Delete session",
    description="Deprecated: Use DELETE /chat/sessions/{session_id} with JWT authentication instead.",
)
async def clear_session_legacy(user_id: str, session_id: str):
    """[DEPRECATED] Delete session using user_id path parameter."""
    try:
        deleted = await delete_session(session_id, user_id)
        return {"session_id": session_id, "user_id": user_id, "deleted": deleted, "status": "deleted" if deleted else "not_found"}
    except Exception as e:
        logger.error("Failed to delete session", error=str(e), user_id=user_id, session_id=session_id)
        raise HTTPException(status_code=500, detail=f"Failed to delete session: {str(e)}")


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
