"""Ingestion service for processing files and storing in memory services."""

import logging
import os
import asyncio
from typing import Dict, List, Optional, Any, Tuple

from app.services.memory import MemoryService
from app.services.graph import GraphitiService
from app.services.ingestion.file_service import FileService
from app.services.ingestion.parsers import parse_file
from app.services.ingestion.chunking import DocumentChunker

logger = logging.getLogger(__name__)


class IngestionService:
    """Service for ingesting files into memory services."""
    
    def __init__(self):
        """Initialize the ingestion service."""
        self.file_service = FileService()
        self.memory_service = MemoryService()
        self.graphiti_service = GraphitiService()
        self.chunker = DocumentChunker()
        
        # Cache to track processed files by hash
        self._processed_hashes = set()
    
    async def process_file(self, file_path: str, user_id: str) -> Dict[str, Any]:
        """Process a file and store it in memory services.
        
        Args:
            file_path: Path to the file (relative to data dir)
            user_id: User ID to associate with the content
            
        Returns:
            Processing results
        """
        logger.info(f"Processing file: {file_path} for user: {user_id}")
        
        # Validate file
        is_valid, error = self.file_service.validate_file(file_path)
        if not is_valid:
            logger.error(f"File validation failed: {error}")
            return {"error": error, "status": "failed"}
            
        # Get file metadata
        file_metadata = self.file_service.get_file_metadata(file_path)
        
        # Check if file has already been processed (deduplication)
        file_hash = file_metadata.get("hash")
        if file_hash in self._processed_hashes:
            logger.info(f"File already processed (duplicate hash): {file_path}")
            return {"status": "skipped", "reason": "duplicate", "file_path": file_path}
        
        # Read file content
        content, error = self.file_service.read_file(file_path)
        if error:
            logger.error(f"Error reading file: {error}")
            return {"error": error, "status": "failed"}
            
        # Parse file
        full_path = os.path.join(self.file_service.data_dir, file_path)
        parsed_content, parse_metadata = parse_file(full_path, content)
        
        # Merge metadata
        combined_metadata = {**file_metadata, **parse_metadata}
        combined_metadata["source_file"] = file_path
        
        # Chunk document
        logger.info(f"Chunking document: {file_path}")
        chunks = self.chunker.chunk_document(parsed_content, combined_metadata)
        logger.info(f"Created {len(chunks)} chunks")
        
        # Store chunks in Mem0
        mem0_results = []
        failures = 0
        retries = 0
        max_retries = 3
        
        for chunk in chunks:
            # Try up to max_retries times to store each chunk
            for attempt in range(max_retries):
                try:
                    chunk_content = chunk["content"]
                    chunk_metadata = chunk["metadata"]
                    
                    # Add small delay between chunks to avoid SQLite concurrency issues
                    if attempt > 0:
                        await asyncio.sleep(0.5)
                    
                    result = await self.memory_service.add(
                        content=chunk_content,
                        user_id=user_id,
                        metadata=chunk_metadata
                    )
                    
                    if "error" in result:
                        logger.warning(f"Error storing chunk in Mem0: {result['error']}")
                        
                        # Only count specific errors that likely won't be resolved by retrying
                        if "Empty content" in str(result.get('error', '')):
                            failures += 1
                            break  # Don't retry for empty content
                            
                        # If this was the last attempt, count as failure
                        if attempt == max_retries - 1:
                            failures += 1
                        else:
                            retries += 1
                            # Continue to the next attempt
                            continue
                    else:
                        mem0_results.append(result)
                        logger.debug(f"Stored chunk {chunk_metadata['chunk_index']} in Mem0")
                        break  # Success, don't need to retry
                except Exception as e:
                    logger.error(f"Error storing chunk in Mem0: {e}")
                    
                    # If this was the last attempt, count as failure
                    if attempt == max_retries - 1:
                        failures += 1
                    else:
                        retries += 1
                        # Sleep before retrying
                        await asyncio.sleep(1)
        
        # Log a summary of retries and failures
        if retries > 0:
            logger.info(f"Required {retries} retries when storing chunks")
        if failures > 0:
            logger.warning(f"Failed to store {failures} chunks after all retries")
        
        # Create episode in Graphiti even if some chunks failed
        graphiti_result = {}
        try:
            # Only proceed with Graphiti if we stored at least some chunks
            if mem0_results:
                graphiti_result = await self.graphiti_service.add_episode(
                    content=parsed_content[:500],  # Use a summary/preview of content
                    user_id=user_id,
                    metadata={
                        "title": combined_metadata.get("title", os.path.basename(file_path)),
                        "source": "file",
                        "source_file": file_path,
                        "file_hash": file_hash,
                        "mem0_chunks": len(mem0_results),
                        "total_chunks": len(chunks),
                        "failed_chunks": failures
                    }
                )
                logger.info(f"Created episode in Graphiti: {graphiti_result.get('episode_id')}")
            else:
                graphiti_result = {"error": "No chunks were successfully stored in Mem0, skipping Graphiti"}
                logger.warning("No chunks were successfully stored in Mem0, skipping Graphiti")
        except Exception as e:
            logger.error(f"Error creating episode in Graphiti: {e}")
            graphiti_result = {"error": str(e)}
        
        # Add this hash to processed set for deduplication
        self._processed_hashes.add(file_hash)
        
        # Return processing results - consider it a success if at least some chunks were stored
        status = "success" if mem0_results else "partial" if failures < len(chunks) else "failed"
        
        return {
            "status": status,
            "file_path": file_path,
            "chunks": len(chunks),
            "stored_chunks": len(mem0_results),
            "failed_chunks": failures,
            "mem0_results": mem0_results,
            "graphiti_result": graphiti_result
        }
    
    async def process_directory(
        self, 
        directory: Optional[str] = None, 
        user_id: str = "system"
    ) -> Dict[str, Any]:
        """Process all files in a directory.
        
        Args:
            directory: Optional subdirectory to process (relative to data dir)
            user_id: User ID to associate with the content
            
        Returns:
            Processing summary
        """
        logger.info(f"Processing directory: {directory or 'data'} for user: {user_id}")
        
        # List files
        files = self.file_service.list_files(directory)
        
        # Filter for supported files
        supported_files = [f for f in files if f.get("supported", False)]
        logger.info(f"Found {len(supported_files)} supported files out of {len(files)} total")
        
        # Process each file
        results = []
        success_count = 0
        skipped_count = 0
        error_count = 0
        partial_count = 0
        
        for index, file_info in enumerate(supported_files):
            file_path = file_info["path"]
            
            # Add a small delay between files to avoid SQLite concurrency issues
            # But not for the first file
            if index > 0:
                logger.debug(f"Waiting 1 second before processing next file")
                await asyncio.sleep(1)
                
            try:
                logger.info(f"Processing file {index+1}/{len(supported_files)}: {file_path}")
                result = await self.process_file(file_path, user_id)
                
                # Track status counts
                if result.get("status") == "success":
                    success_count += 1
                elif result.get("status") == "skipped":
                    skipped_count += 1
                elif result.get("status") == "partial":
                    partial_count += 1
                else:
                    error_count += 1
                    
                results.append({**result, "file": file_path})
            except Exception as e:
                logger.error(f"Error processing file {file_path}: {e}")
                results.append({"status": "error", "file": file_path, "error": str(e)})
                error_count += 1
        
        # Summarize results
        return {
            "status": "completed",
            "total_files": len(supported_files),
            "successful": success_count,
            "partial": partial_count,
            "skipped": skipped_count,
            "failed": error_count,
            "results": results
        } 