"""
Chat API routes for conversational knowledge retrieval.

Provides endpoints for:
- Creating and managing conversations
- Sending messages and receiving responses
- Streaming chat responses
- Managing conversation history

All endpoints require JWT authentication.
"""

from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from synaptiq.api.middleware.auth import get_current_user
from synaptiq.domain.models import User
from synaptiq.infrastructure.database import get_async_session
from synaptiq.services.chat_service import ChatService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/chat", tags=["Chat"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================


class ConversationCreate(BaseModel):
    """Request to create a new conversation."""
    
    title: Optional[str] = Field(
        None,
        max_length=500,
        description="Conversation title (auto-generated from first message if not provided)",
    )


class ConversationUpdate(BaseModel):
    """Request to update a conversation."""
    
    title: Optional[str] = Field(None, max_length=500, description="New title")


class ConversationResponse(BaseModel):
    """Response containing conversation information."""
    
    id: str = Field(..., description="Conversation ID")
    user_id: str = Field(..., description="User ID")
    title: Optional[str] = Field(None, description="Conversation title")
    preview: Optional[str] = Field(None, description="Preview of first message")
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")


class ConversationListResponse(BaseModel):
    """Response containing list of conversations."""
    
    conversations: list[ConversationResponse]
    total: int


class MessageRequest(BaseModel):
    """Request to send a chat message."""
    
    content: str = Field(
        ...,
        description="Message content",
        min_length=1,
        max_length=10000,
    )
    model_id: Optional[str] = Field(
        None,
        description="LLM model identifier (e.g. 'gpt-5.2', 'claude-4.6-sonnet')",
    )


class CitationResponse(BaseModel):
    """Citation in an assistant response."""
    
    id: Optional[int] = None
    source_id: Optional[str] = None
    source_title: Optional[str] = None
    source_url: Optional[str] = None
    timestamp: Optional[int] = None
    chunk_text: Optional[str] = None


class MessageResponse(BaseModel):
    """Response containing a message."""
    
    id: str = Field(..., description="Message ID")
    conversation_id: str = Field(..., description="Conversation ID")
    role: str = Field(..., description="'user' or 'assistant'")
    content: str = Field(..., description="Message content")
    citations: list[dict] = Field(default_factory=list, description="Source citations")
    concepts_referenced: list[str] = Field(
        default_factory=list,
        description="Concepts from knowledge graph",
    )
    confidence: Optional[float] = Field(None, description="Confidence score")
    source_type: Optional[str] = Field(None, description="Response source type")
    created_at: str = Field(..., description="Creation timestamp")


class MessageListResponse(BaseModel):
    """Response containing list of messages."""
    
    messages: list[MessageResponse]
    conversation_id: str


class ChatResponse(BaseModel):
    """Response from sending a message."""
    
    user_message: MessageResponse
    assistant_message: MessageResponse


# =============================================================================
# DEPENDENCY INJECTION
# =============================================================================


async def get_chat_service(
    session: AsyncSession = Depends(get_async_session),
) -> ChatService:
    """Get ChatService instance (model resolved per-request in handlers)."""
    return ChatService(session)


async def _resolve_chat_service(
    session: AsyncSession,
    user: "User",
    model_id: Optional[str] = None,
) -> ChatService:
    """Build a ChatService wired to the correct LLM provider."""
    from synaptiq.services.user_service import UserService
    from synaptiq.agents.model_config import get_model_info

    info = get_model_info(model_id or "gpt-5.2")
    anthropic_key: Optional[str] = None

    if info.provider == "anthropic":
        user_svc = UserService(session)
        keys = await user_svc.get_decrypted_api_keys(user.id)
        anthropic_key = keys.get("anthropic_api_key")
        if not anthropic_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Anthropic API key not configured. Add it in Settings → API Keys.",
            )

    return ChatService(
        session,
        model_id=model_id,
        anthropic_api_key=anthropic_key,
    )


# =============================================================================
# CONVERSATION ENDPOINTS
# =============================================================================


@router.post(
    "/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new conversation",
)
async def create_conversation(
    body: ConversationCreate,
    user: User = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
) -> ConversationResponse:
    """
    Create a new conversation for the authenticated user.
    
    The title is optional - if not provided, it will be auto-generated
    from the first message.
    """
    conversation = await chat_service.create_conversation(
        user_id=user.id,
        title=body.title,
    )
    
    return ConversationResponse(
        id=conversation.id,
        user_id=conversation.user_id,
        title=conversation.title,
        preview=conversation.preview,
        created_at=conversation.created_at.isoformat(),
        updated_at=conversation.updated_at.isoformat(),
    )


@router.get(
    "/conversations",
    response_model=ConversationListResponse,
    summary="List conversations",
)
async def list_conversations(
    user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=100, description="Maximum results"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    chat_service: ChatService = Depends(get_chat_service),
) -> ConversationListResponse:
    """
    List all conversations for the authenticated user.
    
    Conversations are ordered by most recently updated.
    """
    conversations = await chat_service.list_conversations(
        user_id=user.id,
        limit=limit,
        offset=offset,
    )
    
    return ConversationListResponse(
        conversations=[
            ConversationResponse(
                id=conv.id,
                user_id=conv.user_id,
                title=conv.title,
                preview=conv.preview,
                created_at=conv.created_at.isoformat(),
                updated_at=conv.updated_at.isoformat(),
            )
            for conv in conversations
        ],
        total=len(conversations),
    )


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationResponse,
    summary="Get conversation details",
)
async def get_conversation(
    conversation_id: str,
    user: User = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
) -> ConversationResponse:
    """
    Get details of a specific conversation.
    """
    conversation = await chat_service.get_conversation(
        conversation_id=conversation_id,
        user_id=user.id,
    )
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation not found: {conversation_id}",
        )
    
    return ConversationResponse(
        id=conversation.id,
        user_id=conversation.user_id,
        title=conversation.title,
        preview=conversation.preview,
        created_at=conversation.created_at.isoformat(),
        updated_at=conversation.updated_at.isoformat(),
    )


@router.patch(
    "/conversations/{conversation_id}",
    response_model=ConversationResponse,
    summary="Update conversation",
)
async def update_conversation(
    conversation_id: str,
    body: ConversationUpdate,
    user: User = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
) -> ConversationResponse:
    """
    Update a conversation (e.g., rename it).
    """
    conversation = await chat_service.update_conversation(
        conversation_id=conversation_id,
        user_id=user.id,
        title=body.title,
    )
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation not found: {conversation_id}",
        )
    
    return ConversationResponse(
        id=conversation.id,
        user_id=conversation.user_id,
        title=conversation.title,
        preview=conversation.preview,
        created_at=conversation.created_at.isoformat(),
        updated_at=conversation.updated_at.isoformat(),
    )


@router.delete(
    "/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete conversation",
)
async def delete_conversation(
    conversation_id: str,
    user: User = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
) -> None:
    """
    Delete a conversation and all its messages.
    
    This action is irreversible.
    """
    deleted = await chat_service.delete_conversation(
        conversation_id=conversation_id,
        user_id=user.id,
    )
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation not found: {conversation_id}",
        )


# =============================================================================
# MESSAGE ENDPOINTS
# =============================================================================


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=MessageListResponse,
    summary="Get conversation messages",
)
async def get_messages(
    conversation_id: str,
    user: User = Depends(get_current_user),
    limit: int = Query(default=100, ge=1, le=500, description="Maximum results"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    chat_service: ChatService = Depends(get_chat_service),
) -> MessageListResponse:
    """
    Get all messages in a conversation.
    
    Messages are ordered chronologically (oldest first).
    """
    messages = await chat_service.get_messages(
        conversation_id=conversation_id,
        user_id=user.id,
        limit=limit,
        offset=offset,
    )
    
    return MessageListResponse(
        messages=[
            MessageResponse(
                id=msg.id,
                conversation_id=msg.conversation_id,
                role=msg.role,
                content=msg.content,
                citations=msg.citations or [],
                concepts_referenced=msg.concepts_referenced or [],
                confidence=msg.confidence,
                source_type=msg.source_type,
                created_at=msg.created_at.isoformat(),
            )
            for msg in messages
        ],
        conversation_id=conversation_id,
    )


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=ChatResponse,
    summary="Send a message",
)
async def send_message(
    conversation_id: str,
    body: MessageRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> ChatResponse:
    """
    Send a message to the conversation and get an AI response.
    
    The agent will:
    1. Classify the intent of your query
    2. Search your knowledge graph and/or vector store
    3. Synthesize a response with citations
    
    Returns both the user message and the assistant response.
    """
    logger.info(
        "Sending message",
        conversation_id=conversation_id,
        user_id=user.id,
        content_length=len(body.content),
        model_id=body.model_id,
    )
    
    try:
        chat_service = await _resolve_chat_service(session, user, body.model_id)
        user_message, assistant_message = await chat_service.send_message(
            user_id=user.id,
            conversation_id=conversation_id,
            content=body.content,
        )
        
        return ChatResponse(
            user_message=MessageResponse(
                id=user_message.id,
                conversation_id=user_message.conversation_id,
                role=user_message.role,
                content=user_message.content,
                citations=user_message.citations or [],
                concepts_referenced=user_message.concepts_referenced or [],
                confidence=user_message.confidence,
                source_type=user_message.source_type,
                created_at=user_message.created_at.isoformat(),
            ),
            assistant_message=MessageResponse(
                id=assistant_message.id,
                conversation_id=assistant_message.conversation_id,
                role=assistant_message.role,
                content=assistant_message.content,
                citations=assistant_message.citations or [],
                concepts_referenced=assistant_message.concepts_referenced or [],
                confidence=assistant_message.confidence,
                source_type=assistant_message.source_type,
                created_at=assistant_message.created_at.isoformat(),
            ),
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.error(
            "Message send failed",
            conversation_id=conversation_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process message: {str(e)}",
        )


@router.post(
    "/conversations/{conversation_id}/messages/stream",
    summary="Send a message with streaming response",
)
async def send_message_stream(
    conversation_id: str,
    body: MessageRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Send a message and stream the AI response.
    
    Returns a Server-Sent Events (SSE) stream with:
    - `user_message`: When user message is saved
    - `token`: For each response token
    - `done`: When response is complete
    - `error`: If an error occurs
    """
    chat_service = await _resolve_chat_service(session, user, body.model_id)
    logger.info(
        "Streaming message",
        conversation_id=conversation_id,
        user_id=user.id,
        model_id=body.model_id,
    )
    
    async def event_generator():
        """Generate SSE events from streaming response."""
        try:
            async for event in chat_service.send_message_stream(
                user_id=user.id,
                conversation_id=conversation_id,
                content=body.content,
            ):
                yield {
                    "event": event["event"],
                    "data": event["data"] if isinstance(event["data"], str)
                           else str(event["data"]),
                }
        except ValueError as e:
            yield {
                "event": "error",
                "data": str(e),
            }
        except Exception as e:
            logger.error("Streaming failed", error=str(e))
            yield {
                "event": "error",
                "data": str(e),
            }
    
    return EventSourceResponse(event_generator())


@router.post(
    "/conversations/{conversation_id}/messages/{message_id}/regenerate",
    response_model=MessageResponse,
    summary="Regenerate a response",
)
async def regenerate_response(
    conversation_id: str,
    message_id: str,
    user: User = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
) -> MessageResponse:
    """
    Regenerate an assistant response.
    
    The original response is deleted and a new one is generated
    based on the preceding user message.
    """
    try:
        new_message = await chat_service.regenerate_response(
            user_id=user.id,
            conversation_id=conversation_id,
            message_id=message_id,
        )
        
        return MessageResponse(
            id=new_message.id,
            conversation_id=new_message.conversation_id,
            role=new_message.role,
            content=new_message.content,
            citations=new_message.citations or [],
            concepts_referenced=new_message.concepts_referenced or [],
            confidence=new_message.confidence,
            source_type=new_message.source_type,
            created_at=new_message.created_at.isoformat(),
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(
            "Regeneration failed",
            conversation_id=conversation_id,
            message_id=message_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to regenerate response: {str(e)}",
        )


# =============================================================================
# QUICK CHAT ENDPOINT (for simple use cases)
# =============================================================================


class QuickChatRequest(BaseModel):
    """Request for quick chat (auto-creates conversation)."""
    
    query: str = Field(
        ...,
        description="The user's question",
        min_length=1,
        max_length=10000,
    )
    conversation_id: Optional[str] = Field(
        None,
        description="Existing conversation ID (creates new if not provided)",
    )
    model_id: Optional[str] = Field(
        None,
        description="LLM model identifier",
    )


@router.post(
    "",
    response_model=ChatResponse,
    summary="Quick chat",
)
async def quick_chat(
    body: QuickChatRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> ChatResponse:
    """
    Quick chat endpoint - creates a conversation if needed.
    
    This is a convenience endpoint that:
    1. Creates a new conversation if conversation_id is not provided
    2. Sends the message and returns the response
    
    For more control, use the conversation endpoints directly.
    """
    chat_service = await _resolve_chat_service(session, user, body.model_id)
    conversation_id = body.conversation_id
    
    # Create conversation if not provided
    if not conversation_id:
        conversation = await chat_service.create_conversation(user_id=user.id)
        conversation_id = conversation.id
    
    # Send message
    try:
        user_message, assistant_message = await chat_service.send_message(
            user_id=user.id,
            conversation_id=conversation_id,
            content=body.query,
        )
        
        return ChatResponse(
            user_message=MessageResponse(
                id=user_message.id,
                conversation_id=user_message.conversation_id,
                role=user_message.role,
                content=user_message.content,
                citations=user_message.citations or [],
                concepts_referenced=user_message.concepts_referenced or [],
                confidence=user_message.confidence,
                source_type=user_message.source_type,
                created_at=user_message.created_at.isoformat(),
            ),
            assistant_message=MessageResponse(
                id=assistant_message.id,
                conversation_id=assistant_message.conversation_id,
                role=assistant_message.role,
                content=assistant_message.content,
                citations=assistant_message.citations or [],
                concepts_referenced=assistant_message.concepts_referenced or [],
                confidence=assistant_message.confidence,
                source_type=assistant_message.source_type,
                created_at=assistant_message.created_at.isoformat(),
            ),
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.error("Quick chat failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process chat: {str(e)}",
        )


# =============================================================================
# MODEL LISTING
# =============================================================================


@router.get(
    "/models",
    summary="List available LLM models",
)
async def list_models():
    """Return the catalogue of available chat models."""
    from synaptiq.agents.model_config import AVAILABLE_MODELS

    return {
        "models": [
            {
                "id": m.id,
                "display_name": m.display_name,
                "provider": m.provider,
                "is_reasoning": m.is_reasoning,
            }
            for m in AVAILABLE_MODELS
        ]
    }


# =============================================================================
# HEALTH ENDPOINT
# =============================================================================


@router.get("/health")
async def health_check():
    """Check if the chat service is healthy."""
    return {
        "status": "healthy",
        "service": "chat",
    }
