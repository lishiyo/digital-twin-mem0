"""Celery tasks for file processing."""

import asyncio
import logging
from typing import Dict, List, Optional, Any

from app.worker import celery_app
from app.services.ingestion import IngestionService
from app.services.ingestion.file_service import FileService

logger = logging.getLogger(__name__)


@celery_app.task(name="process_file")
def process_file(file_path: str, user_id: str, scope: str = "user", owner_id: str = None, original_filename: str = None) -> dict:
    """Process an uploaded file and store in Mem0.
    
    Args:
        file_path: Path to the file (relative to data directory)
        user_id: User ID to associate with the content
        scope: Content scope ("user", "twin", or "global")
        owner_id: ID of the owner (user or twin ID, or None for global)
        original_filename: Original uploaded filename before storage
        
    Returns:
        Processing results
    """
    logger.info(f"Starting file processing task for: {file_path}, user: {user_id}, scope: {scope}")
    
    # Initialize service
    ingestion_service = IngestionService()
    
    # Get file service to add original filename to metadata
    file_service = FileService()
    if original_filename:
        # Add original filename to the file's metadata by patching the get_file_metadata method
        original_get_metadata = file_service.get_file_metadata
        def get_metadata_with_original(path):
            metadata = original_get_metadata(path)
            metadata["original_filename"] = original_filename
            return metadata
        
        ingestion_service.file_service.get_file_metadata = get_metadata_with_original
    
    # Process file
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    result = loop.run_until_complete(
        ingestion_service.process_file(
            file_path, 
            user_id,
            scope=scope,
            owner_id=owner_id
        )
    )
    
    logger.info(f"Completed file processing for: {file_path}")
    return result


@celery_app.task(name="process_directory")
def process_directory(
    user_id: str,
    directory: Optional[str] = None, 
    scope: str = "user",
    owner_id: str = None
) -> dict:
    """Process all files in a directory.
    
    Args:
        user_id: User ID to associate with the content
        directory: Optional subdirectory to process (relative to data dir)
        scope: Content scope ("user", "twin", or "global")
        owner_id: ID of the owner (user or twin ID, or None for global)
        
    Returns:
        Processing summary
    """
    logger.info(f"Processing directory: {directory or 'data'} for user: {user_id}, scope: {scope}")
    
    # We need to run our async code in a synchronous context
    ingestion_service = IngestionService()
    
    # Run the async function using asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        # If there's no event loop in this thread, create one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    # Process the directory
    try:
        result = loop.run_until_complete(
            ingestion_service.process_directory(
                user_id,
                directory, 
                scope=scope, 
                owner_id=owner_id
            )
        )
        return result
    except Exception as e:
        logger.error(f"Error processing directory: {e}")
        return {"error": str(e), "status": "failed", "directory": directory} 