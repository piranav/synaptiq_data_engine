"""
WebSocket manager for real-time updates.

Provides:
- Connection management with JWT authentication
- Redis pub/sub for broadcasting events across workers
- Event types for jobs, chat, and graph updates
"""

import asyncio
import json
from typing import Any, Optional

import structlog
from fastapi import WebSocket, WebSocketDisconnect
from jose import JWTError, jwt

from config.settings import get_settings

logger = structlog.get_logger(__name__)


class ConnectionManager:
    """
    WebSocket connection manager.
    
    Manages active WebSocket connections per user and supports
    broadcasting events to specific users or all connected clients.
    """
    
    def __init__(self):
        """Initialize connection manager."""
        self.active_connections: dict[str, list[WebSocket]] = {}
        self._redis_client = None
        self._pubsub_task: Optional[asyncio.Task] = None
        self._running = False
        self.settings = get_settings()
    
    async def _get_redis(self):
        """Lazy initialize Redis client."""
        if self._redis_client is None:
            try:
                import redis.asyncio as redis
                self._redis_client = redis.from_url(
                    self.settings.redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                )
                logger.info("Redis client initialized for WebSocket")
            except ImportError:
                logger.warning("redis package not installed, pub/sub disabled")
            except Exception as e:
                logger.error("Failed to connect to Redis", error=str(e))
        return self._redis_client
    
    async def start_pubsub_listener(self):
        """Start listening to Redis pub/sub for events."""
        redis_client = await self._get_redis()
        if not redis_client:
            return
        
        if self._running:
            return
        
        self._running = True
        
        async def listen():
            try:
                pubsub = redis_client.pubsub()
                await pubsub.subscribe("synaptiq:events")
                logger.info("WebSocket pubsub listener started")
                
                async for message in pubsub.listen():
                    if not self._running:
                        break
                    
                    if message["type"] == "message":
                        try:
                            data = json.loads(message["data"])
                            user_id = data.get("user_id")
                            event = data.get("event")
                            payload = data.get("data", {})
                            
                            if user_id:
                                await self.send_to_user(
                                    user_id=user_id,
                                    event=event,
                                    data=payload,
                                )
                            else:
                                await self.broadcast(event=event, data=payload)
                                
                        except json.JSONDecodeError:
                            logger.warning("Invalid JSON in pubsub message")
                        except Exception as e:
                            logger.error("Error processing pubsub message", error=str(e))
                
                await pubsub.unsubscribe("synaptiq:events")
                
            except Exception as e:
                logger.error("Pubsub listener error", error=str(e))
                self._running = False
        
        self._pubsub_task = asyncio.create_task(listen())
    
    async def stop_pubsub_listener(self):
        """Stop the pub/sub listener."""
        self._running = False
        if self._pubsub_task:
            self._pubsub_task.cancel()
            try:
                await self._pubsub_task
            except asyncio.CancelledError:
                pass
        
        if self._redis_client:
            await self._redis_client.close()
            self._redis_client = None
    
    def verify_token(self, token: str) -> Optional[str]:
        """
        Verify JWT token and extract user_id.
        
        Args:
            token: JWT access token
            
        Returns:
            User ID if valid, None otherwise
        """
        try:
            payload = jwt.decode(
                token,
                self.settings.jwt_secret_key,
                algorithms=[self.settings.jwt_algorithm],
            )
            
            if payload.get("type") != "access":
                return None
            
            return payload.get("sub")
            
        except JWTError:
            return None
    
    async def connect(self, websocket: WebSocket, user_id: str):
        """
        Accept a WebSocket connection for a user.
        
        Args:
            websocket: WebSocket connection
            user_id: Authenticated user ID
        """
        await websocket.accept()
        
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        
        self.active_connections[user_id].append(websocket)
        
        logger.info(
            "WebSocket connected",
            user_id=user_id,
            connection_count=len(self.active_connections[user_id]),
        )
        
        # Send connection confirmation
        await self.send_to_connection(
            websocket,
            event="connected",
            data={"user_id": user_id, "message": "Connected to Synaptiq real-time updates"},
        )
    
    def disconnect(self, websocket: WebSocket, user_id: str):
        """
        Remove a WebSocket connection.
        
        Args:
            websocket: WebSocket connection to remove
            user_id: User ID
        """
        if user_id in self.active_connections:
            try:
                self.active_connections[user_id].remove(websocket)
            except ValueError:
                pass
            
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
            
            logger.info("WebSocket disconnected", user_id=user_id)
    
    async def send_to_connection(
        self,
        websocket: WebSocket,
        event: str,
        data: Any,
    ):
        """
        Send an event to a specific connection.
        
        Args:
            websocket: Target WebSocket
            event: Event type
            data: Event data
        """
        try:
            message = json.dumps({"event": event, "data": data})
            await websocket.send_text(message)
        except Exception as e:
            logger.error("Failed to send WebSocket message", error=str(e))
    
    async def send_to_user(
        self,
        user_id: str,
        event: str,
        data: Any,
    ):
        """
        Send an event to all connections for a user.
        
        Args:
            user_id: Target user ID
            event: Event type
            data: Event data
        """
        if user_id not in self.active_connections:
            return
        
        message = json.dumps({"event": event, "data": data})
        disconnected = []
        
        for websocket in self.active_connections[user_id]:
            try:
                await websocket.send_text(message)
            except Exception:
                disconnected.append(websocket)
        
        # Clean up disconnected sockets
        for ws in disconnected:
            self.disconnect(ws, user_id)
    
    async def broadcast(self, event: str, data: Any):
        """
        Broadcast an event to all connected users.
        
        Args:
            event: Event type
            data: Event data
        """
        message = json.dumps({"event": event, "data": data})
        
        for user_id, connections in list(self.active_connections.items()):
            disconnected = []
            
            for websocket in connections:
                try:
                    await websocket.send_text(message)
                except Exception:
                    disconnected.append(websocket)
            
            for ws in disconnected:
                self.disconnect(ws, user_id)
    
    async def publish_event(
        self,
        user_id: Optional[str],
        event: str,
        data: Any,
    ):
        """
        Publish an event via Redis pub/sub.
        
        This allows events to be broadcast across multiple workers.
        
        Args:
            user_id: Target user ID (None for broadcast)
            event: Event type
            data: Event data
        """
        redis_client = await self._get_redis()
        if not redis_client:
            # Fallback to direct send if Redis not available
            if user_id:
                await self.send_to_user(user_id, event, data)
            else:
                await self.broadcast(event, data)
            return
        
        message = json.dumps({
            "user_id": user_id,
            "event": event,
            "data": data,
        })
        
        await redis_client.publish("synaptiq:events", message)
    
    def get_connection_count(self) -> int:
        """Get total number of active connections."""
        return sum(len(conns) for conns in self.active_connections.values())
    
    def get_user_count(self) -> int:
        """Get number of connected users."""
        return len(self.active_connections)


# Global connection manager instance
manager = ConnectionManager()


# =============================================================================
# EVENT HELPERS
# =============================================================================


class EventType:
    """WebSocket event type constants."""
    
    # Connection events
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    
    # Job events
    JOB_STARTED = "job.started"
    JOB_PROGRESS = "job.progress"
    JOB_COMPLETED = "job.completed"
    JOB_FAILED = "job.failed"
    
    # Chat events
    CHAT_TOKEN = "chat.token"
    CHAT_CITATION = "chat.citation"
    CHAT_COMPLETE = "chat.complete"
    
    # Graph events
    GRAPH_UPDATED = "graph.updated"
    CONCEPT_ADDED = "concept.added"
    CONCEPT_REMOVED = "concept.removed"
    
    # Note events
    NOTE_SYNCED = "note.synced"


async def emit_job_event(
    user_id: str,
    job_id: str,
    event_type: str,
    data: Optional[dict] = None,
):
    """
    Emit a job-related event.
    
    Args:
        user_id: Target user
        job_id: Job identifier
        event_type: Type of job event
        data: Additional event data
    """
    payload = {"job_id": job_id, **(data or {})}
    await manager.publish_event(user_id, event_type, payload)


async def emit_chat_token(
    user_id: str,
    conversation_id: str,
    message_id: str,
    token: str,
):
    """
    Emit a chat token for streaming.
    
    Args:
        user_id: Target user
        conversation_id: Conversation identifier
        message_id: Message identifier
        token: Response token
    """
    await manager.publish_event(
        user_id,
        EventType.CHAT_TOKEN,
        {
            "conversation_id": conversation_id,
            "message_id": message_id,
            "token": token,
        },
    )


async def emit_graph_update(
    user_id: str,
    action: str,
    concept_id: Optional[str] = None,
    concept_label: Optional[str] = None,
):
    """
    Emit a graph update event.
    
    Args:
        user_id: Target user
        action: Update action (added, removed, etc.)
        concept_id: Concept URI
        concept_label: Concept label
    """
    await manager.publish_event(
        user_id,
        EventType.GRAPH_UPDATED,
        {
            "action": action,
            "concept_id": concept_id,
            "label": concept_label,
        },
    )


# =============================================================================
# WEBSOCKET ROUTE HANDLER
# =============================================================================


async def websocket_endpoint(websocket: WebSocket, token: Optional[str] = None):
    """
    WebSocket endpoint handler.
    
    Authenticates the connection via JWT token and manages the
    connection lifecycle.
    
    Args:
        websocket: WebSocket connection
        token: JWT access token (via query param or header)
    """
    # Get token from query params or try to extract from first message
    if not token:
        # Accept first to receive messages
        await websocket.accept()
        try:
            # Wait for auth message
            data = await asyncio.wait_for(websocket.receive_text(), timeout=5.0)
            auth_data = json.loads(data)
            token = auth_data.get("token")
        except asyncio.TimeoutError:
            await websocket.send_text(json.dumps({
                "event": "error",
                "data": {"message": "Authentication timeout"},
            }))
            await websocket.close(code=4001)
            return
        except Exception:
            await websocket.send_text(json.dumps({
                "event": "error",
                "data": {"message": "Invalid authentication message"},
            }))
            await websocket.close(code=4001)
            return
    
    # Verify token
    user_id = manager.verify_token(token) if token else None
    if not user_id:
        try:
            await websocket.send_text(json.dumps({
                "event": "error",
                "data": {"message": "Invalid or expired token"},
            }))
            await websocket.close(code=4001)
        except Exception:
            pass
        return
    
    # Connect (will accept if not already accepted)
    try:
        if websocket.client_state.name == "CONNECTING":
            await manager.connect(websocket, user_id)
        else:
            # Already accepted, just register
            if user_id not in manager.active_connections:
                manager.active_connections[user_id] = []
            manager.active_connections[user_id].append(websocket)
            await manager.send_to_connection(
                websocket,
                event="connected",
                data={"user_id": user_id},
            )
    except Exception as e:
        logger.error("WebSocket connection failed", error=str(e))
        return
    
    try:
        # Keep connection alive and handle incoming messages
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)
                
                # Handle ping
                if message.get("event") == "ping":
                    await manager.send_to_connection(
                        websocket,
                        event="pong",
                        data={"timestamp": message.get("data", {}).get("timestamp")},
                    )
                
            except json.JSONDecodeError:
                await manager.send_to_connection(
                    websocket,
                    event="error",
                    data={"message": "Invalid JSON"},
                )
                
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)
    except Exception as e:
        logger.error("WebSocket error", user_id=user_id, error=str(e))
        manager.disconnect(websocket, user_id)

