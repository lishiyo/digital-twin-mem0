"""Memory API endpoints for checking Mem0 integration."""

from fastapi import APIRouter, Depends, Query, HTTPException, Request, Body
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, List, Optional, Any
import logging
import asyncio

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


@router.get("/memory/{memory_id}")
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


@router.delete("/memory/{memory_id}", status_code=200)
async def delete_memory_by_id(
    memory_id: str,
    current_user: dict = Depends(get_current_user_or_mock),
):
    """
    Delete a specific memory by its ID.
    
    Deletes a single memory from Mem0 using its ID.
    """
    user_id = current_user.get("id", DEFAULT_USER["id"])
    
    try:
        memory_service = MemoryService()
        result = await memory_service.delete(memory_id)
        
        if result.get("error"):
            # Check for not found error (though Mem0 delete might not error on not found)
            if "not found" in str(result.get("error")).lower():
                raise HTTPException(
                    status_code=404,
                    detail=f"Memory {memory_id} not found"
                )
            # Other errors
            raise HTTPException(
                status_code=500,
                detail=f"Failed to delete memory: {result.get('error')}"
            )
            
        if not result.get("success"):
             raise HTTPException(
                status_code=500,
                detail=f"Failed to delete memory {memory_id}"
            )
        
        return {"status": "success", "message": f"Memory {memory_id} deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting memory {memory_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete memory: {str(e)}"
        )


@router.get("/list")
async def list_memories(
    limit: int = Query(10, description="Maximum number of memories to return"),
    offset: int = Query(0, description="Offset for pagination"),
    query: Optional[str] = Query(None, description="Optional search query"),
    current_user: dict = Depends(get_current_user_or_mock),
):
    """
    List memories with pagination.
    
    Returns a paginated list of memories, optionally filtered by a search query.
    """
    user_id = current_user.get("id", DEFAULT_USER["id"])
    
    try:
        memory_service = MemoryService()
        # logger.info(f"Memory list request for user {user_id}: offset={offset}, limit={limit}, query={query}")
        
        # Use appropriate method based on whether a search query is provided
        try:
            if query:
                # If a query is provided, use search
                logger.info(f"Using search with query: {query}")
                memories = await asyncio.wait_for(
                    memory_service.search(
                        user_id=user_id,
                        query=query,
                        limit=limit
                    ),
                    timeout=8  # 8 second timeout
                )
            else:
                # Otherwise use get_all with pagination
                # logger.info(f"Using get_all for listing memories")
                # Get memories with pagination offset
                all_memories = await asyncio.wait_for(
                    memory_service.get_all(
                        user_id=user_id,
                        limit=limit + offset  # Get enough to cover offset
                    ),
                    timeout=8  # 8 second timeout
                )
                
                # Debug: Print structure of first memory if available
                if all_memories and len(all_memories) > 0:
                    first_memory = all_memories[0]
                    logger.info(f"First memory keys: {list(first_memory.keys())}")
                    # Print the first few characters of key fields to help debug
                    if 'memory' in first_memory:
                        mem_preview = first_memory['memory']
                        if isinstance(mem_preview, str):
                            logger.info(f"Memory field content preview: {mem_preview[:100]}...")
                        else:
                            logger.info(f"Memory field type: {type(mem_preview)}")
                    if 'content' in first_memory:
                        content_preview = first_memory['content']
                        if isinstance(content_preview, str):
                            logger.info(f"Content field preview: {content_preview[:100]}...")
                        else:
                            logger.info(f"Content field type: {type(content_preview)}")
                    if 'message' in first_memory:
                        logger.info(f"Message structure: {first_memory['message'] if isinstance(first_memory['message'], str) else list(first_memory['message'].keys()) if isinstance(first_memory['message'], dict) else 'not dict or str'}")
                    if 'name' in first_memory:
                        logger.info(f"Memory name: {first_memory['name']}")
                    if 'metadata' in first_memory:
                        logger.info(f"Metadata keys: {list(first_memory['metadata'].keys())}")
                    if 'categories' in first_memory:
                        logger.info(f"Categories: {first_memory['categories']}")
                    
                # Apply pagination manually
                start_idx = min(offset, len(all_memories))
                end_idx = min(offset + limit, len(all_memories))
                memories = all_memories[start_idx:end_idx]
                logger.info(f"Applied pagination: {start_idx}:{end_idx} from {len(all_memories)} memories")
        except asyncio.TimeoutError:
            logger.error(f"Timeout retrieving memories")
            raise HTTPException(
                status_code=504,
                detail="Request to memory service timed out"
            )
        
        # Check for error responses
        if memories and isinstance(memories, list) and len(memories) > 0 and "error" in memories[0]:
            error_msg = memories[0].get("error", "Unknown error")
            logger.error(f"Error from memory service: {error_msg}")
            raise HTTPException(
                status_code=503,
                detail=f"Memory service error: {error_msg}"
            )
        
        # Debug: Log the structure of memories
        if memories and len(memories) > 0:
            first_mem = memories[0]
            logger.info(f"Memory in response keys: {list(first_mem.keys())}")
            
        logger.info(f"Successfully retrieved {len(memories)} memories")
        return {
            "memories": memories,
            "total": len(memories),
            "limit": limit,
            "offset": offset
        }
    except HTTPException:
        raise
    except asyncio.TimeoutError:
        logger.error("Timeout connecting to memory service")
        raise HTTPException(
            status_code=504,
            detail="Request to memory service timed out"
        )
    except Exception as e:
        logger.error(f"Error listing memories: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list memories: {str(e)}"
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


@router.get("/trigger-graphiti-process/{conversation_id}")
async def trigger_graphiti_process_conversation(
    conversation_id: str,
    current_user: dict = Depends(get_current_user_or_mock),
):
    """
    Manually trigger Graphiti processing for all messages in a conversation.
    
    This endpoint specifically processes the conversation for entity/trait extraction
    and Graphiti knowledge graph creation.
    """
    user_id = current_user.get("id", DEFAULT_USER["id"])
    
    try:
        from app.worker.tasks.graphiti_tasks import process_conversation_graphiti
        
        # Trigger the Celery task
        task = process_conversation_graphiti.delay(conversation_id)
        
        return {
            "status": "processing",
            "conversation_id": conversation_id,
            "task_id": task.id,
            "message": "Graphiti processing has been triggered"
        }
    except Exception as e:
        logger.error(f"Error triggering Graphiti processing for conversation {conversation_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to trigger Graphiti processing: {str(e)}"
        ) 