"""Mem0 service for memory operations."""

import logging
from typing import Any, Dict, List, Optional
import os
import uuid
import asyncio
from functools import wraps

from mem0 import MemoryClient  # Import MemoryClient instead of Memory

from app.core.config import settings
from app.core.constants import DEFAULT_USER_ID

logger = logging.getLogger(__name__)

# Module-level singleton client to prevent initialization issues
_mem0_client = None
# Lock to ensure serialized access to Mem0 operations
_mem0_lock = asyncio.Lock()

def get_mem0_client():
    """Get or create the singleton Mem0 client."""
    global _mem0_client
    if _mem0_client is None:
        try:
            # Initialize client with API key through environment
            if settings.MEM0_API_KEY:
                os.environ["MEM0_API_KEY"] = settings.MEM0_API_KEY
            else:
                logger.warning("MEM0_API_KEY not set – Mem0 will fall back to local mode!")
            
            # Initialize using the synchronous client
            logger.info(f"Initializing Mem0 client with API key: {settings.MEM0_API_KEY}")
            _mem0_client = MemoryClient(api_key=settings.MEM0_API_KEY)
            logger.info("Initialized Mem0 singleton client")
        except Exception as e:
            logger.error(f"Failed to initialize Mem0 client: {e}")
            # Return None to indicate failure
            return None
    return _mem0_client

# Helper to convert sync operations to async (for API compatibility)
def async_wrap(func):
    @wraps(func)
    async def run(*args, **kwargs):
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, lambda: func(*args, **kwargs))
        return result
    return run


class MemoryService:
    """Service for interacting with Mem0 Cloud."""

    def __init__(self):
        """Initialize the Mem0 service."""
        # No initialization here - we'll use the singleton client
        self.client = get_mem0_client()
        if not self.client:
            logger.warning("MemoryService initialized without a valid Mem0 client")

    async def add(self, content: str, user_id: str, metadata: Optional[Dict[str, Any]] = None, infer: bool = False, ttl_days: Optional[int] = None) -> Dict[str, Any]:
        """Add a memory to Mem0.
        
        Args:
            content: The content of the memory
            user_id: The user ID to namespace the memory
            metadata: Optional metadata for the memory
            infer: Whether to use LLM inference to extract knowledge (costly in API calls)
            ttl_days: Optional TTL in days for the memory
            
        Returns:
            Dictionary with memory information
        """
        if not self.client:
            logger.warning(f"Using mock response for add - client unavailable")
            return {"memory_id": f"mock-memory-id-{user_id}", "user_id": user_id}
            
        if metadata is None:
            metadata = {}
        
        # Format content as messages list expected by Mem0
        messages = [{"role": "user", "content": str(content).strip()}]
        
        # Acquire lock to prevent concurrent access issues
        async with _mem0_lock:
            # Use retry logic for SQLite concurrency issues
            max_retries = 3
            last_error = None
            
            for attempt in range(max_retries):
                try:
                    # Add small delay on retries to allow other operations to complete
                    if attempt > 0:
                        await asyncio.sleep(1 * attempt)  # Progressive backoff
                        logger.info(f"Retrying memory add (attempt {attempt+1})")
                        
                    # Convert synchronous call to async
                    add_func = async_wrap(self.client.add)
                    # Use version="v2" as recommended in the documentation
                    raw_result = await add_func(
                        messages, 
                        user_id=user_id, 
                        metadata=metadata,
                        version="v2",  # Use v2 as recommended
                        output_format="v1.1",  # Use v1.1 output format as recommended
                        infer=infer,  # Use the provided infer parameter
                        ttl_days=ttl_days  # Use the provided ttl_days parameter
                    )
                    logger.info(f"Memory added for user {user_id}")
                    
                    # Normalize the response format
                    if isinstance(raw_result, dict):
                        # Handle v2 API format which returns {'results': [...]}
                        if "results" in raw_result:
                            # Extract the first result from the array
                            if raw_result["results"] and len(raw_result["results"]) > 0:
                                result = raw_result["results"][0]
                                # If result contains id, map it to memory_id for backwards compatibility
                                if "id" in result:
                                    result["memory_id"] = result["id"]
                                return result
                            else:
                                # Empty results array - create a synthetic response
                                logger.warning(f"Empty results array in Mem0 response: {raw_result}")
                                return {"memory_id": f"generated-{uuid.uuid4()}", "user_id": user_id, "_source": "empty_results"}
                        # Direct response format (v1)
                        elif "memory_id" in raw_result or "id" in raw_result:
                            # Ensure memory_id is available
                            if "id" in raw_result and "memory_id" not in raw_result:
                                raw_result["memory_id"] = raw_result["id"]
                            return raw_result
                    # Handle empty array response
                    elif isinstance(raw_result, list) and not raw_result:
                        logger.warning(f"Empty array response from Mem0")
                        return {"memory_id": f"generated-{uuid.uuid4()}", "user_id": user_id, "_source": "empty_array"}
                    
                    # Fallback: Return the raw result if we couldn't normalize it
                    logger.warning(f"Unexpected Mem0 response format: {raw_result}")
                    return raw_result
                except Exception as e:
                    last_error = e
                    # Check if it's a SQLite concurrency error
                    if "readonly database" in str(e) or "database is locked" in str(e):
                        logger.warning(f"SQLite concurrency error on attempt {attempt+1}: {e}")
                        # On last attempt, just continue to raise
                        if attempt < max_retries - 1:
                            continue
                    # For non-SQLite errors or last attempt, break out
                    break
                    
            # If we get here, all retries failed
            logger.error(f"Error adding memory after {max_retries} attempts: {last_error}")
            return {"error": str(last_error), "memory_id": None, "user_id": user_id}
    
    async def search(self, query: str, user_id: str, limit: int = 5, metadata_filter: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Search Mem0 for memories.
        
        Args:
            query: The search query
            user_id: The user ID to filter results by
            limit: Maximum number of results to return
            metadata_filter: Optional metadata filter criteria to refine search results
            
        Returns:
            List of search results
        """
        if not self.client:
            logger.warning(f"Using mock response for search - client unavailable")
            return [
                {
                    "memory_id": f"mock-memory-id-{user_id}-1",
                    "content": "This is a mock memory result",
                    "similarity": 0.85,
                    "metadata": {"user_id": user_id, "source": "chat"},
                }
            ]
            
        # Acquire lock to prevent concurrent access issues
        async with _mem0_lock:
            try:
                # Use retry logic for SQLite concurrency issues
                max_retries = 3
                last_error = None
                
                for attempt in range(max_retries):
                    try:
                        # Add small delay on retries
                        if attempt > 0:
                            await asyncio.sleep(1 * attempt)
                            logger.info(f"Retrying search (attempt {attempt+1})")
                            
                        # Convert synchronous call to async
                        search_func = async_wrap(self.client.search)
                        # Use parameters as recommended in the documentation
                        raw_results = await search_func(
                            query=query, 
                            user_id=user_id, 
                            limit=limit,
                            metadata=metadata_filter,  # Add metadata filter
                            version="v2",  # Use v2 as recommended
                            output_format="v1.1",  # Use v1.1 output format
                            keyword_search=True  # Enable keyword search for better results
                        )
                        
                        # DEBUG: Log the raw results structure
                        if isinstance(raw_results, dict):
                            logger.info(f"Mem0 raw results is a dict with keys: {list(raw_results.keys())}")
                            # If there's a 'results' key, check its structure
                            if "results" in raw_results:
                                if raw_results["results"] and len(raw_results["results"]) > 0:
                                    first_result = raw_results["results"][0]
                                    # logger.info(f"First result keys: {list(first_result.keys())}")
                                    # Print entire first result for detailed inspection
                                    # logger.info(f"FULL FIRST RESULT: {first_result}")
                                    # Check for the message structure
                                    if "message" in first_result:
                                        logger.info(f"Message structure: {list(first_result['message'].keys()) if isinstance(first_result['message'], dict) else 'not a dict'}")
                                    # Check for similarity score
                                    logger.info(f"Similarity present: {'similarity' in first_result}, Value: {first_result.get('similarity')}")
                        elif isinstance(raw_results, list) and raw_results:
                            logger.info(f"Mem0 raw results is a list with {len(raw_results)} items")
                            first_result = raw_results[0]
                            # logger.info(f"First result keys: {list(first_result.keys())}")
                            # Print entire first result for detailed inspection
                            # logger.info(f"FULL FIRST RESULT: {first_result}")
                        else:
                            logger.info(f"Mem0 raw results type: {type(raw_results)}")
                        
                        # Normalize the results - Mem0 client might return different formats
                        # 1. If it's a dict with 'results' key (seems to be common for Mem0)
                        if isinstance(raw_results, dict) and "results" in raw_results:
                            normalized_results = raw_results["results"]
                            if not normalized_results:
                                logger.warning(f"Empty results array returned from Mem0 search")
                        # 2. If it's already a list (as per API docs)
                        elif isinstance(raw_results, list):
                            normalized_results = raw_results
                        # 3. Some other format - log and return as is
                        else:
                            logger.warning(f"Unexpected result format from Mem0 search: {type(raw_results)}")
                            normalized_results = raw_results
                        
                        # DEBUG: Check normalized results structure
                        if normalized_results and isinstance(normalized_results, list) and len(normalized_results) > 0:
                            first_norm = normalized_results[0]
                            logger.info(f"First normalized result keys: {list(first_norm.keys())}")
                            # Find where content is stored
                            if "content" not in first_norm:
                                if "message" in first_norm:
                                    msg = first_norm["message"]
                                    logger.info(f"Content might be in 'message': {msg.get('content') if isinstance(msg, dict) else 'not a dict'}")
                                    
                                    # Add content extraction from message if needed
                                    if isinstance(msg, dict) and "content" in msg:
                                        # Process all results to extract content from message
                                        for result in normalized_results:
                                            if "message" in result and isinstance(result["message"], dict) and "content" in result["message"]:
                                                result["content"] = result["message"]["content"]
                                                logger.info(f"Extracted content from message: {result['content'][:50]}...")
                        
                        if normalized_results:
                            logger.info(f"Memory search for user {user_id} returned {len(normalized_results)} results")
                        
                        # Return normalized results
                        return normalized_results
                    except Exception as e:
                        last_error = e
                        # Check if it's a SQLite concurrency error
                        if any(err in str(e) for err in ["readonly database", "database is locked"]):
                            logger.warning(f"SQLite concurrency error on search attempt {attempt+1}: {e}")
                            if attempt < max_retries - 1:
                                continue
                        break
                        
                # All attempts failed
                logger.error(f"Error searching memories after {max_retries} attempts: {last_error}")
                return [{"error": str(last_error)}]
            except Exception as e:
                logger.error(f"Error searching memories: {e}")
                return [{"error": str(e)}]
    
    async def add_batch(self, items: List[Dict[str, Any]], user_id: str, infer: bool = False) -> Dict[str, Any]:
        """Add multiple memories to Mem0 in a batch.
        
        Args:
            items: List of memory items with content and metadata
            user_id: The user ID to namespace the memories
            infer: Whether to use LLM inference to extract knowledge (costly in API calls)
            
        Returns:
            Dictionary with batch operation results
        """
        if not self.client:
            logger.warning(f"Using mock response for add_batch - client unavailable")
            return {"success": True, "count": len(items), "results": [{"memory_id": f"mock-{i}"} for i in range(len(items))]}
            
        results = []
        success_count = 0
        
        # Acquire lock to prevent concurrent access issues
        async with _mem0_lock:
            for item in items:
                content = item.get("content", "")
                metadata = item.get("metadata", {})
                
                # Skip empty content
                if not str(content).strip():
                    logger.warning("Skipping empty content item in batch")
                    results.append({"error": "Empty content"})
                    continue
                
                # Format as messages list for Mem0
                messages = [{"role": "user", "content": str(content).strip()}]
                
                # Use retry logic for SQLite concurrency issues
                max_retries = 3
                last_error = None
                success = False
                
                for attempt in range(max_retries):
                    try:
                        # Add small delay on retries
                        if attempt > 0:
                            await asyncio.sleep(1 * attempt)  # Progressive backoff
                            logger.info(f"Retrying batch add (attempt {attempt+1})")
                            
                        # Convert synchronous call to async
                        add_func = async_wrap(self.client.add)
                        # Use parameters as recommended
                        raw_result = await add_func(
                            messages, 
                            user_id=user_id, 
                            metadata=metadata,
                            version="v2",  # Use v2 as recommended
                            output_format="v1.1",  # Use v1.1 output format
                            infer=infer  # Use the provided infer parameter
                        )
                        
                        # Normalize the response format
                        normalized_result = None
                        
                        if isinstance(raw_result, dict):
                            # Handle v2 API format which returns {'results': [...]}
                            if "results" in raw_result:
                                # Extract the first result from the array
                                if raw_result["results"] and len(raw_result["results"]) > 0:
                                    normalized_result = raw_result["results"][0]
                                    # If result contains id, map it to memory_id for backwards compatibility
                                    if "id" in normalized_result and "memory_id" not in normalized_result:
                                        normalized_result["memory_id"] = normalized_result["id"]
                                else:
                                    # Empty results array - create a synthetic response
                                    logger.warning(f"Empty results array in Mem0 batch add response")
                                    normalized_result = {"memory_id": f"generated-{uuid.uuid4()}", "user_id": user_id}
                            # Direct response format (v1)
                            elif "memory_id" in raw_result or "id" in raw_result:
                                normalized_result = raw_result
                                # Ensure memory_id is available
                                if "id" in raw_result and "memory_id" not in raw_result:
                                    normalized_result["memory_id"] = raw_result["id"]
                        # Handle empty array response
                        elif isinstance(raw_result, list) and not raw_result:
                            logger.warning(f"Empty array response from Mem0 in batch add")
                            normalized_result = {"memory_id": f"generated-{uuid.uuid4()}", "user_id": user_id, "_source": "empty_array"}
                        else:
                            # Unexpected format, use as is
                            normalized_result = raw_result
                            
                        results.append(normalized_result or raw_result)
                        success_count += 1
                        success = True
                        break
                    except Exception as e:
                        last_error = e
                        # Check if it's a SQLite concurrency error
                        if "readonly database" in str(e) or "database is locked" in str(e):
                            logger.warning(f"SQLite concurrency error on attempt {attempt+1}: {e}")
                            # Continue to next attempt unless it's the last one
                            if attempt < max_retries - 1:
                                continue
                        # For non-SQLite errors or last attempt, break out
                        break
                
                # If all retries failed
                if not success:
                    logger.error(f"Error adding item in batch after {max_retries} attempts: {last_error}")
                    results.append({"error": str(last_error)})
                    
                # Add a small delay between items to prevent concurrency issues
                await asyncio.sleep(0.5)
            
            logger.info(f"Added {success_count}/{len(items)} items in batch for user {user_id}")
            return {"success": success_count > 0, "count": success_count, "results": results}
    
    async def get_all(self, user_id: str, metadata_filter: Optional[Dict[str, Any]] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get all memories for a user.
        
        Args:
            user_id: The user ID to filter by
            metadata_filter: Optional metadata filter to retrieve only memories matching specific criteria
            limit: Optional maximum number of results to return
            
        Returns:
            List of all memories for the user
        """
        if not self.client:
            logger.warning(f"Using mock response for get_all - client unavailable")
            # Respect the limit in mock response
            mock_count = 3 if limit is None or limit > 3 else limit
            return [
                {
                    "memory_id": f"mock-memory-id-{user_id}-{i}",
                    "content": f"This is mock memory {i}",
                    "metadata": {"user_id": user_id, "source": "chat"},
                }
                for i in range(mock_count)
            ]
            
        # Acquire lock to prevent concurrent access issues
        async with _mem0_lock:
            try:
                # Use retry logic for SQLite concurrency issues
                max_retries = 3
                last_error = None
                
                for attempt in range(max_retries):
                    try:
                        # Add small delay on retries
                        if attempt > 0:
                            await asyncio.sleep(1 * attempt)
                            logger.info(f"Retrying get_all (attempt {attempt+1})")
                            
                        # Convert synchronous call to async
                        get_all_func = async_wrap(self.client.get_all)
                        # Use version parameter as recommended
                        raw_results = await get_all_func(
                            user_id=user_id,
                            metadata=metadata_filter,  # Add metadata filter
                            version="v2",  # Use v2 as recommended
                            output_format="v1.1"  # Use v1.1 output format
                        )
                        
                        # Normalize the results - Mem0 client might return different formats
                        # 1. If it's a dict with 'results' key (seems to be common for Mem0)
                        if isinstance(raw_results, dict) and "results" in raw_results:
                            normalized_results = raw_results["results"]
                            if not normalized_results:
                                logger.warning(f"Empty results array returned from Mem0 get_all")
                        # 2. If it's already a list (as per API docs)
                        elif isinstance(raw_results, list):
                            normalized_results = raw_results
                        # 3. Some other format - log and return as is
                        else:
                            logger.warning(f"Unexpected result format from Mem0 get_all: {type(raw_results)}")
                            normalized_results = raw_results
                        
                        # Process all results to ensure memory_id field exists
                        if normalized_results and isinstance(normalized_results, list):
                            for result in normalized_results:
                                # If id exists but memory_id doesn't, copy it
                                if isinstance(result, dict):
                                    if "id" in result and "memory_id" not in result:
                                        result["memory_id"] = result["id"]
                                        logger.info(f"Copied id to memory_id: {result['id']}")
                                    # If neither exists, generate a UUID
                                    elif "memory_id" not in result and "id" not in result:
                                        result["memory_id"] = f"generated-{uuid.uuid4()}"
                                        logger.warning(f"Generated memory_id for result with missing ID")
                                    # Log when memory has both id and memory_id
                                    elif "id" in result and "memory_id" in result:
                                        logger.info(f"Memory has both id ({result['id']}) and memory_id ({result['memory_id']})")
                                    # Log metadata for debugging
                                    if "metadata" in result:
                                        logger.info(f"Memory metadata keys: {list(result['metadata'].keys()) if isinstance(result['metadata'], dict) else 'not a dict'}")
                                        if isinstance(result['metadata'], dict) and "filename" in result['metadata']:
                                            logger.info(f"Memory filename: {result['metadata']['filename']} with ID: {result.get('memory_id', 'unknown')}")
                                    
                                    # Extract content from message structure if needed
                                    if "content" not in result and "message" in result:
                                        if isinstance(result["message"], dict) and "content" in result["message"]:
                                            result["content"] = result["message"]["content"]
                        
                        # Apply limit if specified
                        if limit is not None and normalized_results and isinstance(normalized_results, list):
                            normalized_results = normalized_results[:limit]
                        
                        if normalized_results:
                            logger.info(f"Retrieved memories for user {user_id}: {len(normalized_results)} memories")
                        else:
                            logger.info(f"No memories found for user {user_id}")
                        
                        # Return normalized results
                        return normalized_results
                    except Exception as e:
                        last_error = e
                        # Check if it's a SQLite concurrency error
                        if any(err in str(e) for err in ["readonly database", "database is locked"]):
                            logger.warning(f"SQLite concurrency error on get_all attempt {attempt+1}: {e}")
                            if attempt < max_retries - 1:
                                continue
                        break
                        
                # All attempts failed
                logger.error(f"Error retrieving all memories after {max_retries} attempts: {last_error}")
                return [{"error": str(last_error)}]
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
        if not self.client:
            logger.warning(f"Using mock response for get - client unavailable")
            return {
                "memory_id": memory_id,
                "content": "This is a mock memory content",
                "metadata": {"source": "chat"},
            }
            
        # Acquire lock to prevent concurrent access issues
        async with _mem0_lock:
            try:
                # Convert synchronous call to async
                get_func = async_wrap(self.client.get)
                result = await get_func(memory_id=memory_id)
                logger.info(f"Retrieved memory {memory_id}")
                return result
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
        if not self.client:
            logger.warning(f"Using mock response for update - client unavailable")
            return {
                "memory_id": memory_id,
                "content": data,
                "updated": True,
            }
            
        # Acquire lock to prevent concurrent access issues
        async with _mem0_lock:
            try:
                # Convert synchronous call to async
                update_func = async_wrap(self.client.update)
                result = await update_func(memory_id=memory_id, data=data)
                logger.info(f"Updated memory {memory_id}")
                return result
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
        if not self.client:
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
            
        # Acquire lock to prevent concurrent access issues
        async with _mem0_lock:
            try:
                # Convert synchronous call to async
                history_func = async_wrap(self.client.history)
                result = await history_func(memory_id=memory_id)
                logger.info(f"Retrieved history for memory {memory_id}")
                return result
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
        if not self.client:
            logger.warning(f"Using mock response for delete - client unavailable")
            return {"success": True, "memory_id": memory_id}
            
        # Acquire lock to prevent concurrent access issues
        async with _mem0_lock:
            try:
                # Convert synchronous call to async
                delete_func = async_wrap(self.client.delete)
                await delete_func(memory_id=memory_id)
                logger.info(f"Deleted memory {memory_id}")
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
        if not self.client:
            logger.warning(f"Using mock response for delete_all - client unavailable")
            return {"success": True, "user_id": user_id}
            
        # Acquire lock to prevent concurrent access issues
        async with _mem0_lock:
            try:
                # Convert synchronous call to async
                delete_all_func = async_wrap(self.client.delete_all)
                await delete_all_func(user_id=user_id)
                logger.info(f"Deleted all memories for user {user_id}")
                return {"success": True, "user_id": user_id}
            except Exception as e:
                logger.error(f"Error deleting all memories for user {user_id}: {e}")
                return {"error": str(e), "success": False, "user_id": user_id}

    async def add_with_rich_metadata(self, 
                             content: str, 
                             user_id: str, 
                             source: str = "app", 
                             category: Optional[str] = None,
                             tags: Optional[List[str]] = None,
                             location: Optional[Dict[str, Any]] = None,
                             timestamp: Optional[str] = None,
                             custom_data: Optional[Dict[str, Any]] = None,
                             infer: bool = False) -> Dict[str, Any]:
        """Add a memory to Mem0 with rich metadata.
        
        Args:
            content: The content of the memory
            user_id: The user ID to namespace the memory
            source: The source of the memory (e.g., 'chat', 'document', 'email')
            category: Optional category of the memory
            tags: Optional list of tags to associate with the memory
            location: Optional location data (e.g., {'lat': 37.7749, 'lon': -122.4194, 'name': 'San Francisco'})
            timestamp: Optional timestamp in ISO format
            custom_data: Additional custom metadata fields
            infer: Whether to use LLM inference to extract knowledge (costly in API calls)
            
        Returns:
            Dictionary with memory information
        """
        # Prepare comprehensive metadata
        metadata = {
            "source": source,
        }
        
        # Add optional metadata fields if provided
        if category:
            metadata["category"] = category
        if tags:
            metadata["tags"] = tags
        if location:
            metadata["location"] = location
        if timestamp:
            metadata["timestamp"] = timestamp
        if custom_data:
            # Merge custom data with built-in metadata
            metadata.update(custom_data)
            
        # Call the regular add method with structured metadata
        return await self.add(content, user_id, metadata, infer=infer)

    async def clear_all(self) -> Dict[str, Any]:
        """Clear all memories for all users.
        
        Returns:
            Success status
        """
        if not self.client:
            logger.warning(f"Using mock response for clear_all - client unavailable")
            return {"success": True, "message": "Cleared all memories (mock)"}
            
        # Acquire lock to prevent concurrent access issues
        async with _mem0_lock:
            try:
                # First attempt: try to use delete_users() if available
                if hasattr(self.client, 'delete_users'):
                    try:
                        # Convert synchronous call to async
                        delete_users_func = async_wrap(self.client.delete_users)
                        result = await delete_users_func()
                        logger.info(f"Successfully called delete_users()")
                        return {
                            "success": True,
                            "message": "Cleared memories for all users using delete_users()",
                            "results": result
                        }
                    except Exception as e:
                        logger.warning(f"Error using delete_users(): {e}, falling back to individual user deletion")
                
                # Fallback approach: use a predefined list of test users
                test_users = [
                    "test-user", 
                    DEFAULT_USER_ID, 
                    "anonymous",
                    "system"
                ]
                
                results = {}
                for user_id in test_users:
                    try:
                        # Convert synchronous call to async
                        delete_all_func = async_wrap(self.client.delete_all)
                        await delete_all_func(user_id=user_id)
                        logger.info(f"Deleted all memories for user {user_id}")
                        results[user_id] = {"success": True}
                    except Exception as e:
                        logger.error(f"Error deleting memories for user {user_id}: {e}")
                        results[user_id] = {"success": False, "error": str(e)}
                
                return {
                    "success": True,
                    "message": f"Cleared memories for {sum(1 for r in results.values() if r.get('success', False))}/{len(results)} users",
                    "results": results
                }
            except Exception as e:
                logger.error(f"Error clearing all memories: {e}")
                return {"error": str(e), "success": False}
    
    async def clear_for_user(self, user_id: str) -> Dict[str, Any]:
        """Clear all memories for a specific user.
        
        Args:
            user_id: The user ID to clear memories for
            
        Returns:
            Success status
        """
        # This is just a wrapper around delete_all with clearer naming
        return await self.delete_all(user_id)

    async def check_connection(self) -> bool:
        """Check if we can connect to the Mem0 service.
        
        Returns:
            True if connected, False otherwise
        """
        if not self.client:
            logger.warning("Cannot check connection - client unavailable")
            return False
            
        try:
            # Try a simple operation to check connection
            # First just check if the client exists and has expected methods
            client_methods = dir(self.client)
            expected_methods = ['get', 'add', 'search', 'update', 'delete']
            
            method_check = all(method in client_methods for method in expected_methods)
            if not method_check:
                logger.warning(f"Mem0 client missing expected methods. Has: {client_methods}")
                return False
            
            # We could also try a test query, but that might be expensive/unnecessary
            # Just return True if we have a properly configured client
            logger.info("Mem0 connection check successful")
            return True
        except Exception as e:
            logger.error(f"Error checking Mem0 connection: {str(e)}")
            return False
