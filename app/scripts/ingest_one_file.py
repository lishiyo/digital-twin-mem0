#!/usr/bin/env python
"""Script to ingest a single file.

This script processes one specific file from the data directory.
"""

import asyncio
import logging
import sys
import json
import os
from pathlib import Path

# Add the parent directory to the path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.core.config import settings
from app.services.ingestion import IngestionService
from app.services.memory import MemoryService
from app.services.graph import GraphitiService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Verify config is loaded
logger.info(f"Using entity extractor type: {settings.ENTITY_EXTRACTOR_TYPE}")
if settings.GEMINI_API_KEY:
    logger.info(f"GEMINI_API_KEY is configured in settings (length: {len(settings.GEMINI_API_KEY)})")
else:
    logger.warning("GEMINI_API_KEY not found in settings, will fall back to spaCy")


async def ingest_file(file_path: str, user_id: str = "test-user", scope: str = "user", owner_id: str = None):
    """Ingest a single file.
    
    Args:
        file_path: Path to the file (relative to data directory)
        user_id: User ID to associate with the content
        scope: Content scope ("user", "twin", or "global")
        owner_id: ID of the owner (user or twin ID, or None for global)
    """
    # Initialize services
    ingestion_service = IngestionService()
    memory_service = MemoryService()
    graphiti_service = GraphitiService()
    
    # For user scope, the owner_id should be the user_id if not explicitly provided
    if scope == "user" and owner_id is None:
        owner_id = user_id
    
    # Process the file
    logger.info(f"Processing file: {file_path} with scope: {scope}, owner_id: {owner_id}")
    result = await ingestion_service.process_file(file_path, user_id, scope=scope, owner_id=owner_id)
    
    # Log basic processing results
    logger.info(f"Processing status: {result.get('status')}")
    logger.info(f"Created {result.get('chunks')} chunks, stored {result.get('stored_chunks')}, skipped {result.get('skipped_chunks', 0)}")
    
    # Log entity extraction results
    if "entities" in result:
        entity_count = result["entities"].get("count", 0)
        entities = result["entities"].get("created", [])
        logger.info(f"Extracted {entity_count} entities from the document")
        
        if entities:
            logger.info("Top entities extracted:")
            for i, entity in enumerate(entities[:5]):  # Show first 5 entities
                logger.info(f"  {i+1}. {entity.get('text')} ({entity.get('type')})")
    
    # Log relationship results
    if "relationships" in result:
        rel_count = result["relationships"].get("count", 0)
        rels = result["relationships"].get("created", [])
        logger.info(f"Created {rel_count} relationships in Graphiti")
        
        if rels:
            logger.info("Top relationships created:")
            for i, rel in enumerate(rels[:5]):  # Show first 5 relationships
                logger.info(f"  {i+1}. {rel.get('source')} --[{rel.get('type')}]--> {rel.get('target')}")
    
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
        logger.info(f"Memory search results: {search_result}")
        
        # Test searching for entities in Graphiti
        if entity_count > 0 and entities:
            # Try to search for the first entity
            first_entity = entities[0]["text"]
            logger.info(f"Searching Graphiti for entity: {first_entity}")
            graph_search = await graphiti_service.node_search(first_entity, limit=3)
            logger.info(f"Found {len(graph_search)} results in Graphiti")
            
            if graph_search:
                logger.info("First Graphiti search result:")
                logger.info(json.dumps(graph_search[0], indent=2, default=str))
    
    return result


if __name__ == "__main__":
    # Get file path from command line, default to a simple MD file
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        # Default to a small Markdown file
        file_path = "5 Things A Day.md"
    
    user_id = f"ingest-test-{Path(file_path).stem.replace(' ', '_')}"
    scope = "user"  # Default scope
    owner_id = user_id  # For user scope, owner_id is the user_id
    
    result = asyncio.run(ingest_file(file_path, user_id, scope=scope, owner_id=owner_id))
    
    # Print summary
    logger.info("-" * 60)
    logger.info("Ingestion Summary:")
    
    if result.get("status") == "success":
        logger.info("✅ File ingestion successful!")
        logger.info(f"  Chunks: {result.get('chunks')}")
        logger.info(f"  Stored in Mem0: {result.get('stored_chunks')}")
        logger.info(f"  Entities extracted: {result.get('entities', {}).get('count', 0)}")
        logger.info(f"  Relationships created: {result.get('relationships', {}).get('count', 0)}")
        logger.info(f"  Scope: {result.get('scope')}")
        logger.info(f"  Owner ID: {result.get('owner_id')}")
    elif result.get("status") == "partial":
        logger.info("⚠️ File ingestion partially successful!")
        logger.info(f"  Scope: {result.get('scope')}")
        logger.info(f"  Owner ID: {result.get('owner_id')}")
    else:
        logger.error("❌ File ingestion failed!")
        logger.error(f"  Error: {result.get('error', 'Unknown error')}")
        sys.exit(1) 