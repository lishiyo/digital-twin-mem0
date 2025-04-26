"""Chat API endpoints for the digital twin."""

from fastapi import APIRouter, Depends, Query, HTTPException, Request, Body
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, List, Optional, Any
import asyncio
import logging
from pydantic import BaseModel, Field
from uuid import uuid4

from app.api.deps import get_current_user, get_db, security, get_current_user_or_mock
from app.services.agent.graph_agent import TwinAgent
from app.core.config import settings
from app.core.constants import DEFAULT_USER
from app.db.models.chat_message import MessageRole
from app.services.conversation.service import ConversationService
from app.worker.celery_app import celery_app
from app.worker.tasks.conversation_tasks import summarize_conversation as summarize_conversation_task
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.conversation.mem0_ingestion_sync import SyncChatMem0Ingestion

logger = logging.getLogger(__name__)
router = APIRouter()

# Optional security scheme that doesn't raise an error for missing credentials
optional_security = HTTPBearer(auto_error=False)

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

@router.post("")
async def chat(
    request: ChatRequest,
    current_user: dict = Depends(get_current_user_or_mock),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Send a message to the digital twin.
    
    Returns the assistant's response.
    """
    try:
        user_id = current_user.get("id", DEFAULT_USER["id"])
        
        # Create conversation service
        conversation_service = ConversationService(db)
        
        # Get or create conversation
        conversation = None
        if request.conversation_id:
            conversation = await conversation_service.get_conversation(
                conversation_id=request.conversation_id,
                user_id=user_id
            )
        
        if not conversation:
            # Create new conversation
            conversation = await conversation_service.create_conversation(
                user_id=user_id,
                meta_data=request.metadata
            )
        
        logger.info(f"Using conversation {conversation.id} for chat message")
        
        # Store user message
        user_message, _ = await conversation_service.add_message(
            conversation_id=conversation.id,
            user_id=user_id,
            content=request.message,
            role=MessageRole.USER,
            meta_data=request.metadata
        )
        user_message_id = str(user_message.id)
        
        # Create agent and get response
        agent = TwinAgent(db)
        response = await agent.chat(
            user_message=request.message,
            user_id=user_id,
            conversation_id=conversation.id
        )
        
        # Store assistant response
        assistant_message, _ = await conversation_service.add_message(
            conversation_id=conversation.id,
            user_id=user_id,
            content=response,
            role=MessageRole.ASSISTANT,
            meta_data=request.metadata
        )
        logger.info(f"Assistant message stored with ID: {assistant_message.id}")
        
        # --- Run Celery tasks in separate threads --- 
        mem0_task_future = asyncio.to_thread(
            celery_app.send_task,
            'app.worker.tasks.conversation_tasks.process_chat_message',
            args=[user_message_id],
            kwargs={}
        )
        logger.info(f"Queuing process_chat_message task for message {user_message_id}")
        
        check_summary_task_future = asyncio.to_thread(
            celery_app.send_task,
            'app.worker.tasks.conversation_tasks.check_and_queue_summarization',
            args=[str(conversation.id)],
            kwargs={}
        )
        logger.info(f"Queuing check_and_queue_summarization task for conversation {conversation.id}")
        
        # Await both task queuing operations concurrently
        mem0_task, check_summary_task = await asyncio.gather(
            mem0_task_future,
            check_summary_task_future
        )
        # --- End Celery task queuing --- 
        
        # Log actual task IDs after awaiting
        logger.info(f"Successfully queued process_chat_message task {mem0_task.id}")
        logger.info(f"Successfully queued check_and_queue_summarization task {check_summary_task.id}")
         
        return {
            "conversation_id": conversation.id,
            "message": response,
            "mem0_task_id": mem0_task.id if mem0_task else None 
        }
        
    except Exception as e:
        logger.error(f"Error in chat endpoint processing: {str(e)}", exc_info=True) # Add traceback
        # Rollback potentially needed if DB operations before error failed
        # await db.rollback() # Consider adding rollback if appropriate
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred during chat processing: {str(e)}"
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
                    "is_stored_in_graphiti": msg.is_stored_in_graphiti,
                    "is_processed_in_summary": msg.processed_in_summary,
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
        
        # Calculate ttl_days using the same logic as in ingestion service
        ttl_days = None
        if message.importance_score is not None:
            # We're just using this to access the ttl calculation method, so we can
            # pass a mock session
            ingestion_service = SyncChatMem0Ingestion(None)
            ttl_days = ingestion_service._get_ttl_for_importance(message.importance_score)
        
        return {
            "message_id": str(message.id),
            "is_stored_in_mem0": message.is_stored_in_mem0,
            "mem0_memory_id": message.mem0_message_id,
            "importance_score": message.importance_score,
            "ttl_days": ttl_days,
            "processed": message.processed_in_mem0,
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


@router.get("/messages/{message_id}")
async def get_message(
    message_id: str,
    current_user: dict = Depends(get_current_user_or_mock),
    db: AsyncSession = Depends(get_db),
):
    """
    Get details for a specific chat message.
    
    Returns the message content and metadata.
    """
    user_id = current_user.get("id", DEFAULT_USER["id"])
    
    try:
        from sqlalchemy import select
        from app.db.models.chat_message import ChatMessage
        from app.db.models.conversation import Conversation
        from app.services.conversation.mem0_ingestion_sync import SyncChatMem0Ingestion
        
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
        
        # Calculate ttl_days using the same logic as in ingestion service
        ttl_days = None
        if message.importance_score is not None:
            # Create instance of SyncChatMem0Ingestion to use its method
            ingestion_service = SyncChatMem0Ingestion(None)
            ttl_days = ingestion_service._get_ttl_for_importance(message.importance_score)
        
        # Return message details
        return {
            "id": str(message.id),
            "conversation_id": str(message.conversation_id),
            "role": message.role.value,
            "content": message.content,
            "timestamp": message.created_at.isoformat(),
            "metadata": message.meta_data,
            "is_stored_in_mem0": message.is_stored_in_mem0,
            "is_stored_in_graphiti": message.is_stored_in_graphiti,
            "processed_in_mem0": message.processed_in_mem0,
            "processed_in_graphiti": message.processed_in_graphiti,
            "processed_in_summary": message.processed_in_summary,
            "importance_score": message.importance_score,
            "ttl_days": ttl_days
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting message {message_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get message: {str(e)}"
        )


@router.post("/conversations/{conversation_id}/summarize")
async def summarize_conversation(
    conversation_id: str,
    current_user: dict = Depends(get_current_user_or_mock),
    db: AsyncSession = Depends(get_db),
):
    """
    Manually trigger summarization of a conversation.
    
    Returns the generated summary and updates the conversation.
    """
    user_id = current_user.get("id", DEFAULT_USER["id"])
    
    try:
        # First verify that the user has access to this conversation
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
        
        # Queue the summarization task
        task = summarize_conversation_task.delay(conversation_id)
        
        return {
            "status": "pending",
            "task_id": task.id,
            "conversation_id": conversation_id,
            "message": "Summarization queued successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error queuing summarization for conversation {conversation_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to queue summarization: {str(e)}"
        )


@router.post("/conversations/{conversation_id}/generate-title")
async def generate_conversation_title(
    conversation_id: str,
    current_user: dict = Depends(get_current_user_or_mock),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate a title for a conversation.
    
    Returns the generated title and updates the conversation.
    """
    user_id = current_user.get("id", DEFAULT_USER["id"])
    
    try:
        # First verify that the user has access to this conversation
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
        
        # Import the summarization service
        from app.services.conversation.summarization import ConversationSummarizationService
        from app.services.memory import MemoryService
        
        # Create the summarization service
        memory_service = MemoryService()
        summarization_service = ConversationSummarizationService(db, memory_service)
        
        # Generate title
        result = await summarization_service.generate_conversation_title(conversation_id)
        
        if result["status"] == "error":
            raise HTTPException(
                status_code=500,
                detail=f"Failed to generate title: {result['reason']}"
            )
        
        return {
            "status": "success",
            "conversation_id": conversation_id,
            "title": result["title"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating title for conversation {conversation_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate title: {str(e)}"
        )


@router.get("/conversations/context")
async def get_previous_conversation_context(
    current_user: dict = Depends(get_current_user_or_mock),
    current_conversation_id: Optional[str] = Query(None, description="Current conversation ID (optional)"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get context from previous conversations for a new conversation.
    
    This endpoint supports context preservation between sessions by retrieving
    summaries from previous conversations.
    """
    user_id = current_user.get("id", DEFAULT_USER["id"])
    
    try:
        # Import the summarization service
        from app.services.conversation.summarization import ConversationSummarizationService
        from app.services.memory import MemoryService
        
        # Create the summarization service
        memory_service = MemoryService()
        summarization_service = ConversationSummarizationService(db, memory_service)
        
        # Get context from previous conversations
        context = await summarization_service.get_previous_conversation_context(
            user_id=user_id,
            current_conversation_id=current_conversation_id or ""
        )
        
        return {
            "status": "success",
            "context": context,
            "has_context": bool(context)
        }
        
    except Exception as e:
        logger.error(f"Error getting previous conversation context for user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get previous conversation context: {str(e)}"
        )
