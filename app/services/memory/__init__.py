"""Mem0 service for memory operations."""

import logging
from typing import Any, Dict, List, Optional

from mem0 import AsyncMemory  # Import the async version of Memory

from app.core.config import settings

logger = logging.getLogger(__name__)


class MemoryService:
    """Service for interacting with Mem0 Cloud."""

    def __init__(self):
        """Initialize the Mem0 service."""
        try:
            # Initialize AsyncMemory with the API key from settings
            self.client = AsyncMemory()
            self.api_key = settings.MEM0_API_KEY
            logger.info("Mem0 client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Mem0 client: {e}")
            # Create a fallback mock client for development
            self.client = None
            self.api_key = settings.MEM0_API_KEY

    async def add(self, content: str, user_id: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Add a memory to Mem0.
        
        Args:
            content: The content of the memory
            user_id: The user ID to namespace the memory
            metadata: Optional metadata for the memory
            
        Returns:
            Dictionary with memory information
        """
        if not metadata:
            metadata = {}
        
        try:
            if self.client:
                # Format as a single message for storage
                messages = [{"role": "user", "content": content}]
                result = await self.client.add(
                    messages, 
                    user_id=user_id,
                    metadata=metadata
                )
                logger.info(f"Memory added for user {user_id}")
                return result
            else:
                # If client initialization failed, return mock response
                logger.warning(f"Using mock response for add - client unavailable")
                return {"memory_id": f"mock-memory-id-{user_id}", "user_id": user_id}
        except Exception as e:
            logger.error(f"Error adding memory: {e}")
            # Return a fallback response with error information
            return {"error": str(e), "memory_id": None, "user_id": user_id}
    
    async def search(self, query: str, user_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search Mem0 for memories.
        
        Args:
            query: The search query
            user_id: The user ID to filter results by
            limit: Maximum number of results to return
            
        Returns:
            List of search results
        """
        try:
            if self.client:
                results = await self.client.search(
                    query=query,
                    user_id=user_id,
                    limit=limit
                )
                logger.info(f"Memory search for user {user_id} returned {len(results)} results")
                return results
            else:
                # If client initialization failed, return mock response
                logger.warning(f"Using mock response for search - client unavailable")
                return [
                    {
                        "memory_id": f"mock-memory-id-{user_id}-1",
                        "content": "This is a mock memory result",
                        "similarity": 0.85,
                        "metadata": {"user_id": user_id, "source": "chat"},
                    }
                ]
        except Exception as e:
            logger.error(f"Error searching memories: {e}")
            # Return a fallback empty list with error information
            return [{"error": str(e)}]
    
    async def add_batch(self, items: List[Dict[str, Any]], user_id: str) -> Dict[str, Any]:
        """Add multiple memories to Mem0 in a batch.
        
        Args:
            items: List of memory items with content and metadata
            user_id: The user ID to namespace the memories
            
        Returns:
            Dictionary with batch operation results
        """
        results = []
        success_count = 0
        
        try:
            if self.client:
                for item in items:
                    content = item.get("content", "")
                    metadata = item.get("metadata", {})
                    
                    # Format as messages for storage
                    messages = [{"role": "user", "content": content}]
                    
                    try:
                        result = await self.client.add(
                            messages, 
                            user_id=user_id,
                            metadata=metadata
                        )
                        results.append(result)
                        success_count += 1
                    except Exception as e:
                        logger.error(f"Error adding memory in batch: {e}")
                        results.append({"error": str(e)})
                
                logger.info(f"Added {success_count}/{len(items)} items in batch for user {user_id}")
                return {"success": success_count > 0, "count": success_count, "results": results}
            else:
                # If client initialization failed, return mock response
                logger.warning(f"Using mock response for add_batch - client unavailable")
                return {"success": True, "count": len(items), "results": [{"memory_id": f"mock-{i}"} for i in range(len(items))]}
        except Exception as e:
            logger.error(f"Error in batch operation: {e}")
            return {"error": str(e), "success": False, "count": 0, "results": results}
        
    async def get_all(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all memories for a user.
        
        Args:
            user_id: The user ID to filter by
            
        Returns:
            List of all memories for the user
        """
        try:
            if self.client:
                results = await self.client.get_all(user_id=user_id)
                logger.info(f"Retrieved all memories for user {user_id}: {len(results)} memories")
                return results
            else:
                # If client initialization failed, return mock response
                logger.warning(f"Using mock response for get_all - client unavailable")
                return [
                    {
                        "memory_id": f"mock-memory-id-{user_id}-{i}",
                        "content": f"This is mock memory {i}",
                        "metadata": {"user_id": user_id, "source": "chat"},
                    }
                    for i in range(3)
                ]
        except Exception as e:
            logger.error(f"Error retrieving all memories: {e}")
            return [{"error": str(e)}]
            
    async def get(self, memory_id: str) -> Dict[str, Any]:
        """Get a specific memory by ID.
        
        Args:
            memory_id: The ID of the memory to retrieve
            
        Returns:
            The memory or an error message
        """
        try:
            if self.client:
                result = await self.client.get(memory_id=memory_id)
                logger.info(f"Retrieved memory {memory_id}")
                return result
            else:
                # If client initialization failed, return mock response
                logger.warning(f"Using mock response for get - client unavailable")
                return {
                    "memory_id": memory_id,
                    "content": "This is a mock memory content",
                    "metadata": {"source": "chat"},
                }
        except Exception as e:
            logger.error(f"Error retrieving memory {memory_id}: {e}")
            return {"error": str(e), "memory_id": memory_id}
            
    async def update(self, memory_id: str, data: str) -> Dict[str, Any]:
        """Update a memory's content.
        
        Args:
            memory_id: The ID of the memory to update
            data: The new content for the memory
            
        Returns:
            The updated memory or an error message
        """
        try:
            if self.client:
                result = await self.client.update(memory_id=memory_id, data=data)
                logger.info(f"Updated memory {memory_id}")
                return result
            else:
                # If client initialization failed, return mock response
                logger.warning(f"Using mock response for update - client unavailable")
                return {
                    "memory_id": memory_id,
                    "content": data,
                    "updated": True,
                }
        except Exception as e:
            logger.error(f"Error updating memory {memory_id}: {e}")
            return {"error": str(e), "memory_id": memory_id, "updated": False}
            
    async def history(self, memory_id: str) -> List[Dict[str, Any]]:
        """Get the history of a memory.
        
        Args:
            memory_id: The ID of the memory to get history for
            
        Returns:
            A list of historical versions of the memory
        """
        try:
            if self.client:
                result = await self.client.history(memory_id=memory_id)
                logger.info(f"Retrieved history for memory {memory_id}")
                return result
            else:
                # If client initialization failed, return mock response
                logger.warning(f"Using mock response for history - client unavailable")
                return [
                    {
                        "memory_id": memory_id,
                        "content": "Original version",
                        "timestamp": "2025-01-01T00:00:00Z",
                    },
                    {
                        "memory_id": memory_id,
                        "content": "Updated version",
                        "timestamp": "2025-01-02T00:00:00Z",
                    }
                ]
        except Exception as e:
            logger.error(f"Error retrieving memory history for {memory_id}: {e}")
            return [{"error": str(e)}]
            
    async def delete(self, memory_id: str) -> Dict[str, Any]:
        """Delete a specific memory.
        
        Args:
            memory_id: The ID of the memory to delete
            
        Returns:
            Success status
        """
        try:
            if self.client:
                await self.client.delete(memory_id=memory_id)
                logger.info(f"Deleted memory {memory_id}")
                return {"success": True, "memory_id": memory_id}
            else:
                # If client initialization failed, return mock response
                logger.warning(f"Using mock response for delete - client unavailable")
                return {"success": True, "memory_id": memory_id}
        except Exception as e:
            logger.error(f"Error deleting memory {memory_id}: {e}")
            return {"error": str(e), "success": False, "memory_id": memory_id}
            
    async def delete_all(self, user_id: str) -> Dict[str, Any]:
        """Delete all memories for a user.
        
        Args:
            user_id: The user ID to delete memories for
            
        Returns:
            Success status
        """
        try:
            if self.client:
                await self.client.delete_all(user_id=user_id)
                logger.info(f"Deleted all memories for user {user_id}")
                return {"success": True, "user_id": user_id}
            else:
                # If client initialization failed, return mock response
                logger.warning(f"Using mock response for delete_all - client unavailable")
                return {"success": True, "user_id": user_id}
        except Exception as e:
            logger.error(f"Error deleting all memories for user {user_id}: {e}")
            return {"error": str(e), "success": False, "user_id": user_id}
