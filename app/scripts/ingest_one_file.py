#!/usr/bin/env python
"""Script to ingest a single file.

This script processes one specific file from the data directory.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add the parent directory to the path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services.ingestion import IngestionService
from app.services.memory import MemoryService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def ingest_file(file_path: str, user_id: str = "test-user"):
    """Ingest a single file.
    
    Args:
        file_path: Path to the file (relative to data directory)
        user_id: User ID to associate with the content
    """
    # Initialize services
    ingestion_service = IngestionService()
    memory_service = MemoryService()
    
    # Process the file
    logger.info(f"Processing file: {file_path}")
    result = await ingestion_service.process_file(file_path, user_id)
    logger.info(f"Processing result: {result}")
    
    # Check if we can retrieve the memories
    if result.get("status") in ["success", "partial"]:
        # Get all memories for the user
        memories = await memory_service.get_all(user_id)
        
        # Check the structure of memories - it might not be a list
        if isinstance(memories, dict):
            logger.info(f"Retrieved memories for user {user_id}: {memories}")
        elif isinstance(memories, list):
            logger.info(f"Retrieved {len(memories)} memories for user {user_id}")
            
            # Print up to 5 memories if available
            memory_count = min(len(memories), 5)
            for i in range(memory_count):
                logger.info(f"Memory {i}: {memories[i]}")
        else:
            logger.info(f"Retrieved memories of type {type(memories)}: {memories}")
            
        # Try searching for something relevant to the file
        search_result = await memory_service.search("What topics are discussed?", user_id, limit=3)
        logger.info(f"Search results: {search_result}")
    
    return result


if __name__ == "__main__":
    # Get file path from command line, default to a simple MD file
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        # Default to a small Markdown file
        file_path = "5 Things A Day.md"
    
    user_id = f"ingest-test-{Path(file_path).stem.replace(' ', '_')}"
    result = asyncio.run(ingest_file(file_path, user_id))
    
    if result.get("status") == "success":
        logger.info("✅ File ingestion successful!")
    elif result.get("status") == "partial":
        logger.info("⚠️ File ingestion partially successful!")
    else:
        logger.error("❌ File ingestion failed!")
        sys.exit(1) 