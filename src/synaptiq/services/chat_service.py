"""
Chat service for managing conversations and messages.

Handles:
- Conversation CRUD operations
- Message persistence
- Integration with QueryAgent for responses
- Session history for agent context
"""

from datetime import datetime, timezone
from typing import Any, AsyncIterator, Optional

import structlog
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from synaptiq.agents import QueryAgent, QueryResponse
from synaptiq.domain.models import Conversation, Message

logger = structlog.get_logger(__name__)


class ChatService:
    """
    Service for chat operations.
    
    Coordinates between:
    - PostgreSQL (conversations, messages)
    - QueryAgent (knowledge retrieval and synthesis)
    """
    
    def __init__(
        self,
        session: AsyncSession,
        query_agent: Optional[QueryAgent] = None,
    ):
        """
        Initialize chat service.
        
        Args:
            session: SQLAlchemy async session
            query_agent: QueryAgent instance (lazy initialized if not provided)
        """
        self.session = session
        self._query_agent = query_agent
    
    @property
    def query_agent(self) -> QueryAgent:
        """Lazy-initialize QueryAgent."""
        if self._query_agent is None:
            self._query_agent = QueryAgent()
        return self._query_agent
    
    # =========================================================================
    # CONVERSATION OPERATIONS
    # =========================================================================
    
    async def create_conversation(
        self,
        user_id: str,
        title: Optional[str] = None,
    ) -> Conversation:
        """
        Create a new conversation.
        
        Args:
            user_id: User ID
            title: Optional conversation title
            
        Returns:
            Created Conversation
        """
        conversation = Conversation(
            user_id=user_id,
            title=title,
        )
        self.session.add(conversation)
        await self.session.flush()
        await self.session.refresh(conversation)
        
        logger.info(
            "Conversation created",
            conversation_id=conversation.id,
            user_id=user_id,
        )
        
        return conversation
    
    async def get_conversation(
        self,
        conversation_id: str,
        user_id: str,
        include_messages: bool = False,
    ) -> Optional[Conversation]:
        """
        Get a conversation by ID.
        
        Args:
            conversation_id: Conversation ID
            user_id: User ID (for ownership verification)
            include_messages: Whether to eager load messages
            
        Returns:
            Conversation if found and owned by user, None otherwise
        """
        query = select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
        )
        
        if include_messages:
            query = query.options(selectinload(Conversation.messages))
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def list_conversations(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Conversation]:
        """
        List conversations for a user, ordered by most recent.
        
        Args:
            user_id: User ID
            limit: Maximum results
            offset: Pagination offset
            
        Returns:
            List of Conversations
        """
        result = await self.session.execute(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())
    
    async def update_conversation(
        self,
        conversation_id: str,
        user_id: str,
        title: Optional[str] = None,
    ) -> Optional[Conversation]:
        """
        Update a conversation.
        
        Args:
            conversation_id: Conversation ID
            user_id: User ID (for ownership verification)
            title: New title
            
        Returns:
            Updated Conversation or None if not found
        """
        # Build update values
        updates = {}
        if title is not None:
            updates["title"] = title
        updates["updated_at"] = datetime.now(timezone.utc)
        
        if not updates:
            return await self.get_conversation(conversation_id, user_id)
        
        await self.session.execute(
            update(Conversation)
            .where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
            )
            .values(**updates)
        )
        
        return await self.get_conversation(conversation_id, user_id)
    
    async def delete_conversation(
        self,
        conversation_id: str,
        user_id: str,
    ) -> bool:
        """
        Delete a conversation and all its messages.
        
        Args:
            conversation_id: Conversation ID
            user_id: User ID (for ownership verification)
            
        Returns:
            True if deleted, False if not found
        """
        result = await self.session.execute(
            delete(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
            )
        )
        
        deleted = result.rowcount > 0
        if deleted:
            logger.info(
                "Conversation deleted",
                conversation_id=conversation_id,
                user_id=user_id,
            )
        
        return deleted
    
    # =========================================================================
    # MESSAGE OPERATIONS
    # =========================================================================
    
    async def get_messages(
        self,
        conversation_id: str,
        user_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Message]:
        """
        Get messages for a conversation.
        
        Args:
            conversation_id: Conversation ID
            user_id: User ID (for ownership verification)
            limit: Maximum results
            offset: Pagination offset
            
        Returns:
            List of Messages ordered by creation time
        """
        # First verify conversation ownership
        conversation = await self.get_conversation(conversation_id, user_id)
        if not conversation:
            return []
        
        result = await self.session.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())
    
    async def _save_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        citations: Optional[list[dict]] = None,
        concepts_referenced: Optional[list[str]] = None,
        retrieval_metadata: Optional[dict] = None,
        confidence: Optional[float] = None,
        source_type: Optional[str] = None,
    ) -> Message:
        """
        Save a message to the database.
        
        Args:
            conversation_id: Conversation ID
            role: 'user' or 'assistant'
            content: Message content
            citations: List of citation dicts (for assistant)
            concepts_referenced: List of concept labels (for assistant)
            retrieval_metadata: Retrieval info (for assistant)
            confidence: Confidence score (for assistant)
            source_type: Source type (for assistant)
            
        Returns:
            Created Message
        """
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            citations=citations or [],
            concepts_referenced=concepts_referenced or [],
            retrieval_metadata=retrieval_metadata,
            confidence=confidence,
            source_type=source_type,
        )
        self.session.add(message)
        await self.session.flush()
        await self.session.refresh(message)
        
        # Update conversation's updated_at and preview
        updates = {"updated_at": datetime.now(timezone.utc)}
        if role == "user":
            updates["preview"] = content[:200] if content else None
        
        await self.session.execute(
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(**updates)
        )
        
        return message
    
    async def _get_conversation_history(
        self,
        conversation_id: str,
        max_messages: int = 20,
    ) -> list[dict[str, str]]:
        """
        Get conversation history for agent context.
        
        Args:
            conversation_id: Conversation ID
            max_messages: Maximum messages to include
            
        Returns:
            List of message dicts with role and content
        """
        result = await self.session.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(max_messages)
        )
        messages = list(result.scalars().all())
        
        # Reverse to get chronological order
        messages.reverse()
        
        return [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]
    
    # =========================================================================
    # CHAT OPERATIONS (with Agent)
    # =========================================================================
    
    async def send_message(
        self,
        user_id: str,
        conversation_id: str,
        content: str,
    ) -> tuple[Message, Message]:
        """
        Send a message and get agent response.
        
        Args:
            user_id: User ID
            conversation_id: Conversation ID
            content: User message content
            
        Returns:
            Tuple of (user_message, assistant_message)
            
        Raises:
            ValueError: If conversation not found or not owned by user
        """
        # Verify conversation ownership
        conversation = await self.get_conversation(conversation_id, user_id)
        if not conversation:
            raise ValueError(f"Conversation not found: {conversation_id}")
        
        # Save user message
        user_message = await self._save_message(
            conversation_id=conversation_id,
            role="user",
            content=content,
        )
        
        # Auto-generate title from first message if not set
        if not conversation.title:
            # Use first 50 chars of first message as title
            title = content[:50] + ("..." if len(content) > 50 else "")
            await self.update_conversation(conversation_id, user_id, title=title)
        
        logger.info(
            "User message saved",
            conversation_id=conversation_id,
            message_id=user_message.id,
        )
        
        try:
            # Get agent response
            # Use conversation_id as session_id for the agent
            response = await self.query_agent.query(
                user_id=user_id,
                query=content,
                session_id=conversation_id,
            )
            
            # Save assistant message
            assistant_message = await self._save_message(
                conversation_id=conversation_id,
                role="assistant",
                content=response.answer,
                citations=[c.model_dump() for c in response.citations],
                concepts_referenced=response.concepts_referenced,
                retrieval_metadata=response.retrieval_metadata.model_dump()
                    if response.retrieval_metadata else None,
                confidence=response.confidence,
                source_type=response.source_type,
            )
            
            logger.info(
                "Assistant response saved",
                conversation_id=conversation_id,
                message_id=assistant_message.id,
                confidence=response.confidence,
            )
            
            return user_message, assistant_message
            
        except Exception as e:
            logger.error(
                "Failed to get agent response",
                conversation_id=conversation_id,
                error=str(e),
            )
            
            # Save error message as assistant response
            assistant_message = await self._save_message(
                conversation_id=conversation_id,
                role="assistant",
                content="I apologize, but I encountered an error while processing your query. Please try again.",
                source_type="error",
                confidence=0.0,
            )
            
            return user_message, assistant_message
    
    async def send_message_stream(
        self,
        user_id: str,
        conversation_id: str,
        content: str,
    ) -> AsyncIterator[dict[str, Any]]:
        """
        Send a message and stream the agent response.
        
        Args:
            user_id: User ID
            conversation_id: Conversation ID
            content: User message content
            
        Yields:
            Event dicts with type and data
            
        Raises:
            ValueError: If conversation not found or not owned by user
        """
        # Verify conversation ownership
        conversation = await self.get_conversation(conversation_id, user_id)
        if not conversation:
            raise ValueError(f"Conversation not found: {conversation_id}")
        
        # Save user message
        user_message = await self._save_message(
            conversation_id=conversation_id,
            role="user",
            content=content,
        )
        
        # Auto-generate title from first message if not set
        if not conversation.title:
            title = content[:50] + ("..." if len(content) > 50 else "")
            await self.update_conversation(conversation_id, user_id, title=title)
        
        # Yield user message event
        yield {
            "event": "user_message",
            "data": {
                "message_id": user_message.id,
                "conversation_id": conversation_id,
            },
        }
        
        # Collect streamed content for saving
        full_content = []
        
        try:
            # Stream agent response
            async for chunk in self.query_agent.query_stream(
                user_id=user_id,
                query=content,
                session_id=conversation_id,
            ):
                full_content.append(chunk)
                yield {
                    "event": "token",
                    "data": chunk,
                }
            
            # Save complete assistant message
            assistant_message = await self._save_message(
                conversation_id=conversation_id,
                role="assistant",
                content="".join(full_content),
                source_type="personal_knowledge",  # Default for streaming
            )
            
            # Yield completion event
            yield {
                "event": "done",
                "data": {
                    "message_id": assistant_message.id,
                    "conversation_id": conversation_id,
                },
            }
            
        except Exception as e:
            logger.error(
                "Streaming failed",
                conversation_id=conversation_id,
                error=str(e),
            )
            
            # Save error message
            error_content = "I apologize, but I encountered an error while processing your query."
            await self._save_message(
                conversation_id=conversation_id,
                role="assistant",
                content=error_content,
                source_type="error",
                confidence=0.0,
            )
            
            yield {
                "event": "error",
                "data": str(e),
            }
    
    async def regenerate_response(
        self,
        user_id: str,
        conversation_id: str,
        message_id: str,
    ) -> Message:
        """
        Regenerate an assistant response.
        
        Finds the user message that triggered the response and
        generates a new response.
        
        Args:
            user_id: User ID
            conversation_id: Conversation ID
            message_id: Message ID of the assistant response to regenerate
            
        Returns:
            New assistant Message
            
        Raises:
            ValueError: If message not found or invalid
        """
        # Get the message to regenerate
        result = await self.session.execute(
            select(Message).where(
                Message.id == message_id,
                Message.conversation_id == conversation_id,
            )
        )
        message = result.scalar_one_or_none()
        
        if not message or message.role != "assistant":
            raise ValueError("Invalid message for regeneration")
        
        # Verify conversation ownership
        conversation = await self.get_conversation(conversation_id, user_id)
        if not conversation:
            raise ValueError(f"Conversation not found: {conversation_id}")
        
        # Find the preceding user message
        result = await self.session.execute(
            select(Message)
            .where(
                Message.conversation_id == conversation_id,
                Message.role == "user",
                Message.created_at < message.created_at,
            )
            .order_by(Message.created_at.desc())
            .limit(1)
        )
        user_message = result.scalar_one_or_none()
        
        if not user_message:
            raise ValueError("No user message found for regeneration")
        
        # Delete the old assistant message
        await self.session.execute(
            delete(Message).where(Message.id == message_id)
        )
        
        # Generate new response
        response = await self.query_agent.query(
            user_id=user_id,
            query=user_message.content,
            session_id=conversation_id,
        )
        
        # Save new assistant message
        new_message = await self._save_message(
            conversation_id=conversation_id,
            role="assistant",
            content=response.answer,
            citations=[c.model_dump() for c in response.citations],
            concepts_referenced=response.concepts_referenced,
            retrieval_metadata=response.retrieval_metadata.model_dump()
                if response.retrieval_metadata else None,
            confidence=response.confidence,
            source_type=response.source_type,
        )
        
        logger.info(
            "Response regenerated",
            conversation_id=conversation_id,
            old_message_id=message_id,
            new_message_id=new_message.id,
        )
        
        return new_message
    
    async def close(self):
        """Close connections."""
        if self._query_agent:
            await self._query_agent.close()

