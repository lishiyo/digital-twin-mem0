"""Ingestion service for processing files and storing in memory services."""

import logging
import os
import asyncio
import hashlib
import re
from typing import Dict, List, Optional, Any, Tuple, Set, Literal

from app.services.memory import MemoryService
from app.services.graph import GraphitiService, ContentScope
from app.services.ingestion.file_service import FileService
from app.services.ingestion.parsers import parse_file
from app.services.ingestion.chunking import DocumentChunker
from app.services.ingestion.entity_extraction_factory import get_entity_extractor
from app.services.traits import TraitExtractionService
from app.services.extraction_pipeline import ExtractionPipeline

logger = logging.getLogger(__name__)


class IngestionService:
    """Service for ingesting files into memory services."""
    
    # Constants for entity filtering
    MIN_ENTITY_NAME_LENGTH = 2
    COMMON_TERMS = {"i", "me", "my", "you", "your", "we", "us", "our", "they",
                   "a", "an", "the", "and", "but", "or", "for", "nor", 
                   "on", "at", "to", "from", "with", "in", "out", "up", "down"}
    # Entity and relationship limits now handled by ExtractionPipeline
    
    def __init__(self):
        """Initialize the ingestion service."""
        self.file_service = FileService()
        self.memory_service = MemoryService()
        self.graphiti_service = GraphitiService()
        self.chunker = DocumentChunker()
        self.entity_extractor = get_entity_extractor()
        
        # Get database session - we need to handle this differently since we're in a sync context
        from app.api.deps import sync_get_db
        db_session = next(sync_get_db())
        
        # Initialize trait service with the database session
        self.trait_service = TraitExtractionService(db_session)
        
        # Cache to track processed files by hash
        self._processed_hashes = set()
        # Cache to track processed chunks by content hash
        self._processed_chunk_hashes = set()
        # Cache to track entities already registered in Graphiti
        self._registered_entities = set()
        
        # Create extraction pipeline with all necessary services
        self.extraction_pipeline = ExtractionPipeline(
            entity_extractor=self.entity_extractor,
            trait_service=self.trait_service,
            graphiti_service=self.graphiti_service
        )
    
    async def process_file(self, file_path: str, user_id: str, 
                          scope: ContentScope = "user", 
                          owner_id: str = None) -> Dict[str, Any]:
        """Process a file and store it in memory services.
        
        Args:
            file_path: Path to the file to process
            user_id: ID of the user processing the file
            scope: Content scope ("user", "twin", or "global")
            owner_id: ID of the owner (user or twin ID, or None for global)
            
        Returns:
            Dictionary with processing results
        """
        logger.info(f"Processing file: {file_path} for user: {user_id}, scope: {scope}")
        
        # Validate file exists and is supported
        try:
            is_valid, error = self.file_service.validate_file(file_path)
            if not is_valid:
                logger.error(f"Invalid file: {error}")
                return {"status": "failed", "error": error}
        except Exception as e:
            logger.error(f"Error validating file: {e}")
            return {"status": "failed", "error": str(e)}
        
        # Get file metadata
        try:
            file_metadata = self.file_service.get_file_metadata(file_path)
            file_hash = file_metadata.get("hash", "unknown")
            
            # Skip if we've already processed this file
            if file_hash in self._processed_hashes:
                logger.info(f"File already processed: {file_path} (hash: {file_hash})")
                return {"status": "skipped", "reason": "duplicate", "file_path": file_path}
                
        except Exception as e:
            logger.error(f"Error getting file metadata: {e}")
            return {"status": "failed", "error": str(e)}
        
        # Read file content
        try:
            content, error = self.file_service.read_file(file_path)
            if error:
                logger.error(f"Error reading file: {error}")
                return {"status": "failed", "error": error}
                
            if not content:
                logger.error("File is empty")
                return {"status": "failed", "error": "File is empty"}
                
        except Exception as e:
            logger.error(f"Error reading file: {e}")
            return {"status": "failed", "error": str(e)}
        
        # Parse the file to extract content and metadata
        try:
            parsed_content, parsed_metadata = parse_file(file_path, content)
            
            if not parsed_content:
                logger.error("Failed to parse file content")
                return {"status": "failed", "error": "Failed to parse file content"}
                
            # Combine file metadata with parsed metadata
            combined_metadata = {**file_metadata, **parsed_metadata}
            
        except Exception as e:
            logger.error(f"Error parsing file: {e}")
            return {"status": "failed", "error": str(e)}
        
        # Chunk the document
        try:
            chunks = self.chunker.chunk_document(parsed_content)
            logger.info(f"Created {len(chunks)} chunks from: {file_path}")
            
            if not chunks:
                logger.error("Failed to create chunks")
                return {"status": "failed", "error": "Failed to create chunks"}
                
        except Exception as e:
            logger.error(f"Error chunking document: {e}")
            return {"status": "failed", "error": str(e)}
        
        # For each chunk, add to memory
        failures = 0
        skipped_chunks = 0
        mem0_results = []
        
        for i, chunk in enumerate(chunks):
            # Calculate hash for deduplication
            chunk_hash = hashlib.md5(chunk["content"].encode("utf-8")).hexdigest()
            
            # Skip if we've already processed this exact chunk
            if chunk_hash in self._processed_chunk_hashes:
                skipped_chunks += 1
                continue
                
            # Prepare metadata for this chunk
            chunk_metadata = {
                **combined_metadata,
                "chunk_index": i,
                "total_chunks": len(chunks),
                "source_file": file_path
            }
            
            try:
                # Add to memory
                result = await self.memory_service.add(
                    content=chunk["content"],
                    metadata=chunk_metadata,
                    user_id=user_id
                )
                
                # Remember we've processed this chunk
                self._processed_chunk_hashes.add(chunk_hash)
                
                # Add result to list
                mem0_results.append({
                    "chunk_index": i,
                    "memory_id": result.get("id"),
                    "content_hash": chunk_hash
                })
                
            except Exception as e:
                logger.error(f"Error adding chunk to memory: {e}")
                failures += 1
        
        # Create chunk boundaries for extraction pipeline
        chunk_boundaries = []
        current_offset = 0
        
        for chunk in chunks:
            content_length = len(chunk["content"])
            chunk_boundaries.append((current_offset, current_offset + content_length))
            current_offset += content_length
            
        # Use the extraction pipeline to process the document
        # Only proceed with Graphiti if we stored at least some chunks
        graphiti_result = {}
        entity_results = []
        relationship_results = []
        extraction_result = {}
        traits_result = []
        
        logger.info(f"mem0_results: {mem0_results}")
        if mem0_results:
            # Process document through extraction pipeline with these chunks
            try:
                pipeline_result = await self.extraction_pipeline.process_document(
                    content=parsed_content,
                    user_id=user_id,
                    file_path=file_path,
                    metadata={
                        "file_path": file_path,
                        "title": combined_metadata.get("title", os.path.basename(file_path)),
                        "file_hash": file_hash,
                        "mem0_chunks": len(mem0_results),
                        "total_chunks": len(chunks),
                        "failed_chunks": failures,
                        "skipped_chunks": skipped_chunks,
                        "keywords": combined_metadata.get("keywords", []),
                        "original_filename": combined_metadata.get("original_filename", os.path.basename(file_path)),
                        **combined_metadata
                    },
                    chunk_boundaries=chunk_boundaries,
                    scope=scope,
                    owner_id=owner_id
                )
                
                # Extract results
                graphiti_result = pipeline_result.get("episode", {})
                processing_result = pipeline_result.get("processing", {}) # for entities and relations
                extraction_result = pipeline_result.get("extraction", {}) # for traits
                
                # Get entity and relationship results safely
                entity_results = []
                relationship_results = []
                if processing_result:
                    entity_results = processing_result.get("entities", [])
                    relationship_results = processing_result.get("relationships", [])
                
                # Get traits result safely
                traits_result = []
                if extraction_result:
                    traits_result = extraction_result.get("traits", [])
                    
                logger.info(f"Processed document through extraction pipeline: {len(entity_results)} entities, "
                          f"{len(relationship_results)} relationships, "
                          f"{len(traits_result)} traits")
                
            except Exception as e:
                logger.error(f"Error processing document through extraction pipeline: {e}")
                graphiti_result = {"error": str(e)}
        else:
            graphiti_result = {"error": "No chunks were successfully stored in Mem0, skipping Graphiti"}
            logger.warning("No chunks were successfully stored in Mem0, skipping Graphiti")
            
        # Add this hash to processed set for deduplication
        self._processed_hashes.add(file_hash)
        
        # Prepare final response data
        entities_result = {
            "count": len(entity_results),
            "items": entity_results
        }
        
        relationships_result = {
            "count": len(relationship_results),
            "items": relationship_results
        }

        traits_result = {
            "count": len(traits_result),
            "items": traits_result
        }
        
        logger.info(f"process_file FINAL! entity_results: {entities_result}, relationship_results: {relationships_result}, traits_results: {traits_result}")

        # Define embedding count (one per successful memory chunk)
        embedding_count = len(mem0_results)

        # Return processing results
        status = "success" if mem0_results else "partial" if failures < len(chunks) else "failed"
        
        return {
            "status": status,
            "file_path": file_path,
            "chunks": {
                "count": len(mem0_results),
                "items": mem0_results
            },
            "entities": entities_result,
            "relationships": relationships_result,
            "traits": traits_result,
            "embeddings": {
                "count": embedding_count
            },
            "graphiti_result": graphiti_result,
            "scope": scope,
            "owner_id": owner_id
        }
    
    async def process_directory(
        self, 
        user_id: str,
        directory: Optional[str] = None, 
        scope: ContentScope = "user",
        owner_id: str = None
    ) -> Dict[str, Any]:
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
        
        # List files
        files = self.file_service.list_files(directory)
        
        # Filter for supported
        supported_files = [f for f in files if f.get("supported", False)]
        logger.info(f"Found {len(supported_files)} supported files out of {len(files)} total")
        
        # Process each file
        results = []
        success_count = 0
        skipped_count = 0
        error_count = 0
        partial_count = 0
        entity_count = 0
        relationship_count = 0
        
        for index, file_info in enumerate(supported_files):
            file_path = file_info["path"]
            
            # Add a small delay between files to avoid SQLite concurrency issues
            # But not for the first file
            if index > 0:
                logger.debug(f"Waiting 1 second before processing next file")
                await asyncio.sleep(1)
                
            try:
                logger.info(f"Processing file {index+1}/{len(supported_files)}: {file_path}")
                result = await self.process_file(
                    file_path, 
                    user_id, 
                    scope=scope, 
                    owner_id=owner_id
                )
                
                # Track status counts
                if result.get("status") == "success":
                    success_count += 1
                elif result.get("status") == "skipped":
                    skipped_count += 1
                elif result.get("status") == "partial":
                    partial_count += 1
                else:
                    error_count += 1
                
                # Track entity and relationship counts
                entity_count += result.get("entities", {}).get("count", 0)
                relationship_count += result.get("relationships", {}).get("count", 0)
                    
                results.append({**result, "file": file_path})
            except Exception as e:
                logger.error(f"Error processing file {file_path}: {e}")
                results.append({"status": "error", "file": file_path, "error": str(e)})
                error_count += 1
        
        # Return summary
        return {
            "status": "completed",
            "directory": directory or "data",
            "total_files": len(supported_files),
            "successful": success_count,
            "skipped": skipped_count,
            "failed": error_count,
            "partial": partial_count,
            "entities": entity_count,
            "relationships": relationship_count,
            "results": results,
            "scope": scope,
            "owner_id": owner_id
        } 