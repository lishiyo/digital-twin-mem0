"""Chat API endpoints for the digital twin."""

from fastapi import APIRouter, Depends, Query, HTTPException, Request, Body
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse
from typing import Dict, List, Optional, Any
import asyncio
import logging
from pydantic import BaseModel, Field
from uuid import uuid4

from app.api.deps import get_current_user, get_db, security
from app.services.agent.graph_agent import TwinAgent
from app.core.config import settings
from app.core.constants import DEFAULT_USER
from app.db.models.chat_message import MessageRole
from app.services.conversation.service import ConversationService
from app.worker.celery_app import celery_app
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)
router = APIRouter()

# Model for the chat request
class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = Field(None, description="Conversation ID (optional, creates new if absent)")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Optional metadata for the conversation")

# Model for the conversation response
class ConversationResponse(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int = 0

# Optional security scheme that doesn't raise an error for missing credentials
optional_security = HTTPBearer(auto_error=False)

# Optional authentication dependency - enables testing in development
async def get_current_user_or_mock(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_security),
):
    """Get the current authenticated user or a mock user for development."""
    if credentials:
        try:
            return await get_current_user(credentials)
        except HTTPException:
            # Fall back to mock user if authentication fails
            logger.warning("Authentication failed, using mock user")
            return DEFAULT_USER
    
    # No credentials provided, use mock user
    logger.warning("No authentication provided, using mock user")
    return DEFAULT_USER


@router.post("")
async def chat_with_twin(
    chat_request: ChatRequest,
    user_id: Optional[str] = Query(None, description="User ID to use (defaults to authenticated user)"),
    model_name: str = Query(getattr(settings, "CHAT_MODEL", "gpt-4o-mini"), description="Model to use for response generation"),
    current_user: dict = Depends(get_current_user_or_mock),
    db: AsyncSession = Depends(get_db),
):
    """
    Chat with the digital twin.
    
    This endpoint allows you to send a message to the digital twin agent
    and receive a response. The agent will use the user's personal knowledge base
    to inform its responses.
    
    This implementation now:
    1. Creates or updates a conversation record
    2. Stores user and assistant messages
    3. Triggers asynchronous processing for memory ingestion
    """
    if not user_id:
        user_id = current_user.get("id", DEFAULT_USER["id"])
    
    # Store message IDs for later use with Celery
    user_message_id = None
    assistant_message_id = None
    conversation_id = None
    
    try:
        # Initialize conversation service
        conversation_service = ConversationService(db)
        
        # Get or create conversation
        conversation_id = chat_request.conversation_id
        
        # Initialize the agent
        agent = TwinAgent(user_id=user_id, model_name=model_name)
        
        # Save user message to database
        user_message, conversation = await conversation_service.add_message(
            conversation_id=conversation_id or str(uuid4()),
            user_id=user_id,
            content=chat_request.message,
            role=MessageRole.USER,
            meta_data=chat_request.metadata or {}
        )
        
        # Store IDs for background processing
        user_message_id = user_message.id
        conversation_id = conversation.id
        
        # Process the message from the request body
        assistant_response = await agent.chat(chat_request.message)
        
        # Save assistant response to database
        assistant_message, _ = await conversation_service.add_message(
            conversation_id=conversation.id,
            user_id=user_id,
            content=assistant_response,
            role=MessageRole.ASSISTANT,
            meta_data={"model": model_name}
        )
        
        # Store assistant message ID for background processing
        assistant_message_id = assistant_message.id
        
        # Complete the database transaction and ensure it's closed
        await db.commit()
        await db.close()
        
        # Prepare the response data
        response_data = {
            "user_message": chat_request.message,
            "twin_response": assistant_response,
            "user_id": user_id,
            "model_used": model_name,
            "conversation_id": conversation_id
        }
        
        logger.info(f"Chat messages saved to conversation {conversation_id}")
        
        # Return the response immediately
        return response_data
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process message: {str(e)}"
        )
    finally:
        # Schedule background tasks outside of the async context
        # This is done in a finally block to ensure it happens even if there was an error
        if user_message_id:
            # Use standard task queuing without any sqlalchemy context
            # Use the fully qualified task name
            celery_app.send_task(
                "app.worker.tasks.conversation_tasks.process_chat_message",
                args=[user_message_id],
                countdown=1
            )
        
        if assistant_message_id:
            celery_app.send_task(
                "app.worker.tasks.conversation_tasks.process_chat_message",
                args=[assistant_message_id],
                countdown=2
            )


@router.get("/conversations")
async def list_conversations(
    limit: int = Query(10, description="Maximum number of conversations to return"),
    offset: int = Query(0, description="Offset for pagination"),
    current_user: dict = Depends(get_current_user_or_mock),
    db: AsyncSession = Depends(get_db),
):
    """
    List conversations for the current user.
    
    Returns a paginated list of conversations sorted by last updated time.
    """
    user_id = current_user.get("id", DEFAULT_USER["id"])
    
    try:
        conversation_service = ConversationService(db)
        conversations = await conversation_service.get_user_conversations(
            user_id=user_id,
            limit=limit,
            offset=offset
        )
        
        return {
            "total": len(conversations),
            "offset": offset,
            "limit": limit,
            "conversations": [
                {
                    "id": str(conv.id),
                    "title": conv.title or "Untitled Conversation",
                    "created_at": conv.created_at.isoformat(),
                    "updated_at": conv.updated_at.isoformat(),
                    "summary": conv.summary
                } for conv in conversations
            ]
        }
    except Exception as e:
        logger.error(f"Error listing conversations: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list conversations: {str(e)}"
        )


@router.get("/conversations/{conversation_id}")
async def get_conversation_details(
    conversation_id: str,
    current_user: dict = Depends(get_current_user_or_mock),
    db: AsyncSession = Depends(get_db),
):
    """
    Get details for a specific conversation.
    
    Returns the conversation details and messages.
    """
    user_id = current_user.get("id", DEFAULT_USER["id"])
    
    try:
        conversation_service = ConversationService(db)
        conversation = await conversation_service.get_conversation(
            conversation_id=conversation_id,
            user_id=user_id
        )
        
        if not conversation:
            raise HTTPException(
                status_code=404, 
                detail=f"Conversation {conversation_id} not found"
            )
        
        messages = await conversation_service.get_conversation_messages(
            conversation_id=conversation_id,
            user_id=user_id
        )
        
        return {
            "id": str(conversation.id),
            "title": conversation.title or "Untitled Conversation",
            "created_at": conversation.created_at.isoformat(),
            "updated_at": conversation.updated_at.isoformat(),
            "summary": conversation.summary,
            "metadata": conversation.meta_data,
            "messages": [
                {
                    "id": str(msg.id),
                    "role": msg.role.value,
                    "content": msg.content,
                    "created_at": msg.created_at.isoformat(),
                    "is_stored_in_mem0": msg.is_stored_in_mem0,
                    "importance_score": msg.importance_score
                } for msg in messages
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting conversation {conversation_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get conversation: {str(e)}"
        )


@router.get("/messages/{message_id}/mem0-status")
async def get_message_mem0_status(
    message_id: str,
    current_user: dict = Depends(get_current_user_or_mock),
    db: AsyncSession = Depends(get_db),
):
    """
    Check the Mem0 ingestion status for a specific message.
    
    Returns details about whether the message has been ingested to Mem0.
    """
    user_id = current_user.get("id", DEFAULT_USER["id"])
    
    try:
        from sqlalchemy import select
        from app.db.models.chat_message import ChatMessage
        from app.db.models.conversation import Conversation
        
        # Query to get the message and verify ownership
        query = (
            select(ChatMessage)
            .join(Conversation)
            .where(ChatMessage.id == message_id)
            .where(Conversation.user_id == user_id)
        )
        
        result = await db.execute(query)
        message = result.scalars().first()
        
        if not message:
            raise HTTPException(
                status_code=404, 
                detail=f"Message {message_id} not found or not authorized"
            )
        
        return {
            "message_id": str(message.id),
            "is_stored_in_mem0": message.is_stored_in_mem0,
            "mem0_memory_id": message.mem0_message_id,
            "importance_score": message.importance_score,
            "processed": message.processed,
            "created_at": message.created_at.isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting mem0 status for message {message_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get mem0 status: {str(e)}"
        )
