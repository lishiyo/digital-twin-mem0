#!/usr/bin/env python
"""Test script for Mem0 memory service.

This script tests basic Mem0 operations directly.
"""

import asyncio
import logging
import os
import sys
import uuid
from pathlib import Path

# Add the parent directory to the path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services.memory import MemoryService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def test_memory_service():
    """Test basic memory service operations."""
    # Generate unique test ID
    test_id = str(uuid.uuid4())[:8]
    user_id = f"test-memory-{test_id}"
    
    logger.info(f"Testing memory service with user_id: {user_id}")
    
    # Initialize memory service
    memory_service = MemoryService()
    
    # Test adding a memory
    content = f"This is a test memory from test_memory.py script. Test ID: {test_id}"
    metadata = {
        "source": "test_script",
        "test_id": test_id
    }
    
    logger.info("Testing memory add...")
    add_result = await memory_service.add(content, user_id)
    logger.info(f"Add result: {add_result}")
    
    if "error" in add_result:
        logger.error(f"Add operation failed: {add_result['error']}")
        return
        
    memory_id = add_result.get("memory_id")
    
    # Test searching for the memory
    logger.info("Testing memory search...")
    search_result = await memory_service.search("test memory", user_id, limit=5)
    logger.info(f"Search result: {search_result}")
    
    # Test getting the memory by ID
    if memory_id:
        logger.info(f"Testing get memory by ID: {memory_id}")
        get_result = await memory_service.get(memory_id)
        logger.info(f"Get result: {get_result}")
    
    # Get all memories for user
    logger.info("Testing get all memories...")
    get_all_result = await memory_service.get_all(user_id)
    logger.info(f"Found {len(get_all_result)} memories for user {user_id}")
    
    # Clean up test data
    logger.info("Cleaning up test data...")
    delete_result = await memory_service.delete_all(user_id)
    logger.info(f"Delete result: {delete_result}")
    
    logger.info("Memory service test completed!")
    return {
        "test_id": test_id,
        "user_id": user_id,
        "success": True
    }


if __name__ == "__main__":
    """Run the memory test."""
    asyncio.run(test_memory_service()) 