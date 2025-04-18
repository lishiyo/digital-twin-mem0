"""Ingestion service for processing files and storing in memory services."""

import logging
import os
import asyncio
import hashlib
from typing import Dict, List, Optional, Any, Tuple, Set

from app.services.memory import MemoryService
from app.services.graph import GraphitiService
from app.services.ingestion.file_service import FileService
from app.services.ingestion.parsers import parse_file
from app.services.ingestion.chunking import DocumentChunker
from app.services.ingestion.entity_extraction import EntityExtractor

logger = logging.getLogger(__name__)


class IngestionService:
    """Service for ingesting files into memory services."""
    
    def __init__(self):
        """Initialize the ingestion service."""
        self.file_service = FileService()
        self.memory_service = MemoryService()
        self.graphiti_service = GraphitiService()
        self.chunker = DocumentChunker()
        self.entity_extractor = EntityExtractor()
        
        # Cache to track processed files by hash
        self._processed_hashes = set()
        # Cache to track processed chunks by content hash
        self._processed_chunk_hashes = set()
        # Cache to track entities already registered in Graphiti
        self._registered_entities = set()
    
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
        
        # Extract entities, relationships, and keywords
        if len(parsed_content.strip()) > 0:
            try:
                logger.info(f"Extracting entities from document: {file_path}")
                extraction_results = self.entity_extractor.process_document(parsed_content)
                
                # Add extraction results to metadata
                combined_metadata["entity_extraction"] = {
                    "entity_count": extraction_results["summary"]["entity_count"],
                    "relationship_count": extraction_results["summary"]["relationship_count"],
                    "keyword_count": extraction_results["summary"]["keyword_count"]
                }
                
                # Add top keywords to metadata
                if extraction_results["keywords"]:
                    top_keywords = [k["text"] for k in extraction_results["keywords"][:5]]
                    combined_metadata["keywords"] = top_keywords
            except Exception as e:
                logger.error(f"Error extracting entities: {e}")
                extraction_results = {"entities": [], "relationships": [], "keywords": [], "summary": {"entity_count": 0, "relationship_count": 0, "keyword_count": 0}}
        else:
            extraction_results = {"entities": [], "relationships": [], "keywords": [], "summary": {"entity_count": 0, "relationship_count": 0, "keyword_count": 0}}
        
        # Chunk document with optimized strategy
        logger.info(f"Chunking document: {file_path}")
        chunks = self.chunker.chunk_document(parsed_content, combined_metadata)
        logger.info(f"Created {len(chunks)} chunks")
        
        # Store chunks in Mem0 with deduplication
        mem0_results = []
        failures = 0
        retries = 0
        skipped_chunks = 0
        max_retries = 3
        
        for chunk in chunks:
            # Calculate hash of chunk content for deduplication
            chunk_content = chunk["content"]
            chunk_metadata = chunk["metadata"]
            chunk_hash = hashlib.md5(chunk_content.encode()).hexdigest()
            
            # Skip duplicate chunks
            if chunk_hash in self._processed_chunk_hashes:
                logger.debug(f"Skipping duplicate chunk (hash: {chunk_hash})")
                skipped_chunks += 1
                continue
            
            # Try up to max_retries times to store each chunk
            for attempt in range(max_retries):
                try:
                    # Add small delay between chunks to avoid SQLite concurrency issues
                    if attempt > 0:
                        await asyncio.sleep(0.5)
                    
                    result = await self.memory_service.add(
                        content=chunk_content,
                        user_id=user_id,
                        metadata=chunk_metadata,
                        infer=False  # Disable inference to reduce OpenAI API calls
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
                        # Add chunk hash to processed set
                        self._processed_chunk_hashes.add(chunk_hash)
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
        if skipped_chunks > 0:
            logger.info(f"Skipped {skipped_chunks} duplicate chunks")
        
        # Create episode in Graphiti and add entities/relationships
        graphiti_result = {}
        entity_results = []
        relationship_results = []
        
        try:
            # Only proceed with Graphiti if we stored at least some chunks
            if mem0_results:
                # 1. Create the episode
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
                        "failed_chunks": failures,
                        "skipped_chunks": skipped_chunks,
                        "keywords": combined_metadata.get("keywords", [])
                    }
                )
                logger.info(f"Created episode in Graphiti: {graphiti_result.get('episode_id')}")
                
                # 2. Process entities if we have any
                if extraction_results["entities"]:
                    logger.info(f"Processing {len(extraction_results['entities'])} entities in Graphiti")
                    
                    # Dictionary to map entity text to entity_id
                    entity_id_map = {}
                    
                    # Process each unique entity
                    for entity in extraction_results["entities"]:
                        entity_text = entity["text"]
                        entity_type = entity["entity_type"]
                        
                        # Skip if we've already processed this entity (case-sensitive)
                        entity_key = f"{entity_text}:{entity_type}"
                        if entity_key in self._registered_entities:
                            # If already registered, get its ID from graphiti 
                            # (simplified - in real implementation would need to query)
                            continue
                        
                        # Create entity in Graphiti
                        try:
                            # Prepare entity properties based on entity type
                            entity_properties = {
                                "source_file": file_path,
                                "label": entity["label"],
                                "user_id": user_id,
                                "context": entity["context"][:255] if "context" in entity else ""
                            }
                            
                            # Add the appropriate name/title property based on entity type
                            if entity_type == "Document":
                                entity_properties["title"] = entity_text
                            else:
                                entity_properties["name"] = entity_text
                            
                            entity_id = await self.graphiti_service.create_entity(
                                entity_type=entity_type,
                                properties=entity_properties
                            )
                            
                            # Remember this entity has been registered
                            self._registered_entities.add(entity_key)
                            entity_id_map[entity_text] = entity_id
                            
                            entity_results.append({
                                "entity_id": entity_id,
                                "text": entity_text,
                                "type": entity_type
                            })
                        except Exception as e:
                            logger.error(f"Error creating entity in Graphiti: {e}")
                    
                    # 3. Process relationships
                    if extraction_results["relationships"]:
                        logger.info(f"Processing {len(extraction_results['relationships'])} relationships in Graphiti")
                        
                        # Skip map to avoid duplicate relationships
                        processed_rels = set()
                        
                        for rel in extraction_results["relationships"]:
                            source_text = rel["source"]
                            target_text = rel["target"]
                            rel_type = rel["relationship"]
                            
                            # Skip if we've already processed this relationship
                            rel_key = f"{source_text}:{rel_type}:{target_text}"
                            if rel_key in processed_rels:
                                continue
                            
                            # Get entity IDs if available
                            source_id = entity_id_map.get(source_text)
                            target_id = entity_id_map.get(target_text)
                            
                            # If we have both IDs, create the relationship
                            if source_id and target_id:
                                try:
                                    rel_id = await self.graphiti_service.create_relationship(
                                        source_id=source_id,
                                        target_id=target_id,
                                        rel_type=rel_type,
                                        properties={
                                            "context": rel["context"][:255] if "context" in rel else "",
                                            "source_file": file_path,
                                            "user_id": user_id
                                        }
                                    )
                                    
                                    processed_rels.add(rel_key)
                                    
                                    relationship_results.append({
                                        "relationship_id": rel_id,
                                        "source": source_text,
                                        "target": target_text,
                                        "type": rel_type
                                    })
                                except Exception as e:
                                    logger.error(f"Error creating relationship in Graphiti: {e}")
            else:
                graphiti_result = {"error": "No chunks were successfully stored in Mem0, skipping Graphiti"}
                logger.warning("No chunks were successfully stored in Mem0, skipping Graphiti")
        except Exception as e:
            logger.error(f"Error processing Graphiti operations: {e}")
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
            "skipped_chunks": skipped_chunks,
            "mem0_results": mem0_results,
            "graphiti_result": graphiti_result,
            "entities": {
                "count": len(entity_results),
                "created": entity_results
            },
            "relationships": {
                "count": len(relationship_results),
                "created": relationship_results
            }
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
                
                # Track entity and relationship counts
                entity_count += result.get("entities", {}).get("count", 0)
                relationship_count += result.get("relationships", {}).get("count", 0)
                    
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
            "entities_created": entity_count,
            "relationships_created": relationship_count,
            "results": results
        } 