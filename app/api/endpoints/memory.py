"""Memory API endpoints for checking Mem0 integration."""

from fastapi import APIRouter, Depends, Query, HTTPException, Request, Body
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, List, Optional, Any
import logging

from app.api.deps import get_current_user, get_db, security
from app.core.constants import DEFAULT_USER
from app.services.memory import MemoryService
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)
router = APIRouter()

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


@router.get("/check")
async def check_mem0_connection():
    """Check connection to Mem0 service."""
    try:
        memory_service = MemoryService()
        status = await memory_service.check_connection()
        return {
            "status": "connected" if status else "disconnected",
            "message": "Successfully connected to Mem0" if status else "Failed to connect to Mem0"
        }
    except Exception as e:
        logger.error(f"Error checking Mem0 connection: {str(e)}")
        return {
            "status": "error",
            "message": f"Error connecting to Mem0: {str(e)}"
        }


@router.get("/memory-by-conversation/{conversation_id}")
async def get_memories_by_conversation(
    conversation_id: str,
    limit: int = Query(20, description="Maximum number of memories to return"),
    current_user: dict = Depends(get_current_user_or_mock),
):
    """
    Get memories stored in Mem0 for a specific conversation.
    
    This endpoint retrieves memories that were created from chat messages
    in the specified conversation.
    """
    user_id = current_user.get("id", DEFAULT_USER["id"])
    
    try:
        memory_service = MemoryService()
        
        # Query Mem0 for memories linked to this conversation
        memories = await memory_service.search(
            user_id=user_id,
            query=f"metadata.conversation_id:{conversation_id}",
            limit=limit
        )
        
        return {
            "conversation_id": conversation_id,
            "total": len(memories),
            "memories": memories
        }
    except Exception as e:
        logger.error(f"Error fetching memories for conversation {conversation_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch memories: {str(e)}"
        )


@router.get("/{memory_id}")
async def get_memory_by_id(
    memory_id: str,
    current_user: dict = Depends(get_current_user_or_mock),
):
    """
    Get a specific memory by its ID.
    
    Retrieves a single memory from Mem0 by its ID.
    """
    user_id = current_user.get("id", DEFAULT_USER["id"])
    
    try:
        memory_service = MemoryService()
        memory = await memory_service.get(memory_id)
        
        if not memory:
            raise HTTPException(
                status_code=404,
                detail=f"Memory {memory_id} not found"
            )
        
        return memory
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching memory {memory_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch memory: {str(e)}"
        )


@router.get("/trigger-process-conversation/{conversation_id}")
async def trigger_process_conversation(
    conversation_id: str,
    current_user: dict = Depends(get_current_user_or_mock),
):
    """
    Manually trigger processing for all messages in a conversation.
    
    This is useful for testing or reprocessing messages that might have failed.
    """
    user_id = current_user.get("id", DEFAULT_USER["id"])
    
    try:
        from app.worker.tasks.conversation_tasks import process_conversation
        
        # Trigger the Celery task
        task = process_conversation.delay(conversation_id)
        
        return {
            "status": "processing",
            "conversation_id": conversation_id,
            "task_id": task.id,
            "message": "Processing has been triggered"
        }
    except Exception as e:
        logger.error(f"Error triggering processing for conversation {conversation_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to trigger processing: {str(e)}"
        ) 