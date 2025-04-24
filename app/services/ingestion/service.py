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

logger = logging.getLogger(__name__)


class IngestionService:
    """Service for ingesting files into memory services."""
    
    # Constants for entity filtering
    MIN_ENTITY_NAME_LENGTH = 2
    COMMON_TERMS = {"i", "me", "my", "you", "your", "we", "us", "our", "they",
                   "a", "an", "the", "and", "but", "or", "for", "nor", 
                   "on", "at", "to", "from", "with", "in", "out", "up", "down"}
    MAX_ENTITIES_PER_CHUNK = 20
    MAX_RELATIONSHIPS_TOTAL = 40
    
    def __init__(self):
        """Initialize the ingestion service."""
        self.file_service = FileService()
        self.memory_service = MemoryService()
        self.graphiti_service = GraphitiService()
        self.chunker = DocumentChunker()
        self.entity_extractor = get_entity_extractor()
        
        # Cache to track processed files by hash
        self._processed_hashes = set()
        # Cache to track processed chunks by content hash
        self._processed_chunk_hashes = set()
        # Cache to track entities already registered in Graphiti
        self._registered_entities = set()
    
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
        
        # Extract entities and relationships using Gemini
        extraction_results = {"entities": [], "relationships": []}
        try:
            # Create chunk boundaries for entity extraction
            chunk_boundaries = []
            current_offset = 0
            
            for chunk in chunks:
                content_length = len(chunk["content"])
                chunk_boundaries.append((current_offset, current_offset + content_length))
                current_offset += content_length
            
            # Extract entities and relationships using Gemini
            extraction_results = self.entity_extractor.process_document(
                parsed_content, 
                chunk_boundaries=chunk_boundaries,
                extract_traits=False
            )
            logger.info(f"Extracted {len(extraction_results['entities'])} entities and {len(extraction_results['relationships'])} relationships")
            
            # Extract and process traits for UserProfile
            try:
                # Use TraitExtractionService to extract and process traits
                from sqlalchemy.ext.asyncio import AsyncSession
                from app.db.session import get_db

                # Get database session
                db = await get_db()
                
                # Create trait extraction service
                trait_service = TraitExtractionService(db)
                
                # Extract traits from entire document content
                # This will also update the UserProfile
                trait_result = await trait_service.extract_traits(
                    content=parsed_content,
                    source_type="document",
                    user_id=user_id,
                    metadata={
                        "file_path": file_path,
                        "title": combined_metadata.get("title", os.path.basename(file_path)),
                        **combined_metadata
                    },
                    update_profile=True
                )
                
                logger.info(f"Extracted and processed {len(trait_result.get('traits', []))} traits from document")
                
                # Store trait extraction result for later use
                trait_extraction_result = trait_result
                
                # Add traits to extraction_results to be used by Graphiti
                extraction_results["traits"] = trait_result.get("traits", [])
            except Exception as e:
                logger.error(f"Error extracting traits for UserProfile: {e}")
                trait_extraction_result = {"status": "error", "message": str(e), "traits": []}
            
            # Keep name extraction but remove redundant filtering
            filtered_entities = extraction_results["entities"].copy()
            
            # Keep track of person names to extract from longer texts
            potential_person_names = set()
            
            # First pass: identify potential person names in longer texts
            for entity in extraction_results["entities"]:
                entity_text = entity["text"]
                
                # If we have a long entity text, scan it for potential person names
                if len(entity_text) > 50:
                    # Look for patterns like "with Name," or "and Name " or "Name and"
                    # Find names that follow prepositions or conjunctions
                    name_patterns = [
                        r'with\s+([A-Z][a-z]+)[\s,]',
                        r'and\s+([A-Z][a-z]+)[\s,]', 
                        r'by\s+([A-Z][a-z]+)[\s,]',
                        r'from\s+([A-Z][a-z]+)[\s,]',
                        r'for\s+([A-Z][a-z]+)[\s,]',
                        r'to\s+([A-Z][a-z]+)[\s,]',
                        r'of\s+([A-Z][a-z]+)[\s,]',
                        r'(^|[\s,])([A-Z][a-z]+)(\s+and\s|\s+,\s)'  # Name at beginning or after spaces/commas
                    ]
                    
                    for pattern in name_patterns:
                        matches = re.findall(pattern, entity_text)
                        for match in matches:
                            if isinstance(match, tuple):
                                # If the pattern has multiple capture groups, get the name part
                                for part in match:
                                    if part and part[0].isupper() and len(part) > 1:
                                        potential_person_names.add(part)
                            else:
                                # Single capture group
                                if match and len(match) > 1:
                                    potential_person_names.add(match)
            
            # Add potential person names as new entities
            names_added = 0
            for name in potential_person_names:
                # Check if this is a capitalized acronym or abbreviation
                is_acronym = len(name) <= 3 and name.isupper()
                
                # Keep the same filtering logic for extracted names
                if (
                    (len(name) >= self.MIN_ENTITY_NAME_LENGTH or is_acronym) and
                    (name.lower() not in self.COMMON_TERMS or is_acronym) and
                    not name.isdigit()
                ):
                    logger.info(f"Extracted person name '{name}' from longer text")
                    filtered_entities.append({
                        "text": name,
                        "entity_type": "Person",
                        "chunk_index": 0,  # Default chunk
                        "extracted_from_text": True,
                        "confidence": 0.9
                    })
                    names_added += 1
            
            # Update filtered entities - no separate filtering needed as entity_extraction.py already did it
            logger.info(f"Using {len(filtered_entities)} entities from extraction, added {names_added} extracted person names")
            extraction_results["entities"] = filtered_entities
            
            # Filter relationships to only include valid entities
            valid_entity_texts = {entity["text"] for entity in filtered_entities}
            filtered_relationships = []
            rel_filtered_out = 0
            
            # Process all relationships - no need for special handling of important entities
            # since that's now handled in entity_extraction.py
            for rel in extraction_results["relationships"]:
                source_text = rel["source"]
                target_text = rel["target"]
                
                # Standard check - both entities must be in the filtered list
                if source_text in valid_entity_texts and target_text in valid_entity_texts:
                    filtered_relationships.append(rel)
                else:
                    rel_filtered_out += 1
                    # Log detailed reason for filtering
                    filtered_reason = ""
                    if source_text not in valid_entity_texts and target_text not in valid_entity_texts:
                        filtered_reason = "both source and target entities missing from filtered list"
                    elif source_text not in valid_entity_texts:
                        filtered_reason = f"source entity '{source_text}' missing from filtered list"
                    else:
                        filtered_reason = f"target entity '{target_text}' missing from filtered list"
                        
                    logger.info(f"Filtered out invalid relationship: {rel} (Reason: {filtered_reason})")
            
            # Add relationships for extracted person names
            for name in potential_person_names:
                if name in valid_entity_texts:
                    # Create relationships with other extracted names
                    for other_name in potential_person_names:
                        if name != other_name and other_name in valid_entity_texts:
                            filtered_relationships.append({
                                "source": name,
                                "target": other_name,
                                "relationship": "MENTIONED_WITH",
                                "context": "Co-mentioned in document",
                                "sentence_id": 0,
                                "confidence": 0.8
                            })
                    
                    # Create relationships with longer entities
                    for entity in filtered_entities:
                        entity_text = entity["text"]
                        if len(entity_text) > 50 and name in entity_text and entity_text != name:
                            filtered_relationships.append({
                                "source": name,
                                "target": entity_text,
                                "relationship": "MENTIONED_IN",
                                "context": "Mentioned in longer text",
                                "sentence_id": 0,
                                "confidence": 0.9
                            })
            
            logger.info(f"Filtered out {rel_filtered_out} relationships with invalid entities, {len(filtered_relationships)} remain")
            extraction_results["relationships"] = filtered_relationships
        except Exception as e:
            logger.error(f"Error extracting entities: {e}")
        
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
                        "keywords": combined_metadata.get("keywords", []),
                        "traits": extraction_results["traits"]
                    },
                    scope=scope,
                    owner_id=owner_id
                )
                logger.info(f"Created episode in Graphiti: {graphiti_result.get('episode_id')} with scope {scope}")
                
                # 2. Process entities if we have any
                if extraction_results["entities"]:
                    logger.info(f"Processing {len(extraction_results['entities'])} entities in Graphiti")
                    
                    # Dictionary to map entity text to entity_id
                    entity_id_map = {}
                    
                    # Group entities by chunk
                    entities_by_chunk = {}
                    for entity in extraction_results["entities"]:
                        chunk_idx = entity.get("chunk_index", 0)  # Default to 0 if not set
                        if chunk_idx not in entities_by_chunk:
                            entities_by_chunk[chunk_idx] = []
                        entities_by_chunk[chunk_idx].append(entity)
                    
                    # Create a set to track processed entities within this file
                    processed_entity_keys = set()
                    
                    for chunk_idx, entities in entities_by_chunk.items():
                        # Sort entities by confidence first (highest confidence first), 
                        # then by length (longest first) as a secondary criterion
                        entities.sort(key=lambda e: (-e.get("confidence", 0), -len(e["text"])))
                        
                        # Process up to MAX_ENTITIES_PER_CHUNK entities per chunk
                        chunk_entity_count = 0
                        
                        for entity in entities:
                            # Skip if we've reached the maximum entities for this chunk
                            if chunk_entity_count >= self.MAX_ENTITIES_PER_CHUNK:
                                break
                                
                            entity_text = entity["text"]
                            entity_type = entity["entity_type"]
                            
                            # Skip if we've already processed this entity in this file
                            entity_key = f"{entity_text}:{entity_type}"
                            if entity_key in processed_entity_keys:
                                continue
                            
                            # Remember this entity has been processed in this file
                            processed_entity_keys.add(entity_key)
                            
                            # Check if entity already exists in the graph
                            try:
                                existing_entity = await self.graphiti_service.find_entity(
                                    name=entity_text,
                                    entity_type=entity_type,
                                    scope=scope,
                                    owner_id=owner_id
                                )
                                
                                if existing_entity:
                                    # Entity already exists, use its ID
                                    entity_id = existing_entity.get("id")
                                    entity_id_map[entity_text] = entity_id
                                    logger.info(f"Found existing entity: {entity_text} ({entity_type}) with ID {entity_id}")
                                    
                                    # Add to entity results so it's included in the count even though it wasn't created
                                    entity_results.append({
                                        "entity_id": entity_id,
                                        "text": entity_text,
                                        "type": entity_type,
                                        "scope": scope,
                                        "owner_id": owner_id,
                                        "existing": True
                                    })
                                    
                                    # Count this toward our chunk entity limit
                                    chunk_entity_count += 1
                                    continue
                                else:
                                    # Create a new entity
                                    try:
                                        logger.info(f"Creating entity: {entity_text} ({entity_type})")
                                        
                                        # For Document entities, use 'title' property instead of 'name'
                                        if entity_type == "Document":
                                            entity_properties = {
                                                "title": entity_text,
                                            }
                                        else:
                                            entity_properties = {
                                                "name": entity_text,
                                            }
                                        
                                        entity_id = await self.graphiti_service.create_entity(
                                            entity_type=entity_type,
                                            properties=entity_properties,
                                            scope=scope,
                                            owner_id=owner_id
                                        )
                                        
                                        # Remember this entity's ID
                                        entity_id_map[entity_text] = entity_id
                                        logger.info(f"Added entity '{entity_text}' to ID map with ID: {entity_id}")
                                        
                                        entity_results.append({
                                            "entity_id": entity_id,
                                            "text": entity_text,
                                            "type": entity_type,
                                            "scope": scope,
                                            "owner_id": owner_id,
                                            "existing": False
                                        })
                                        
                                        # Count this toward our chunk entity limit
                                        chunk_entity_count += 1
                                        
                                    except Exception as e:
                                        logger.error(f"Error creating entity in Graphiti: {e}")
                                        continue  # Skip this entity and proceed to the next
                            except Exception as e:
                                logger.error(f"Error checking for existing entity: {e}")
                                continue
                    
                    # 3. Process relationships
                    if extraction_results["relationships"]:
                        logger.info(f"Processing {len(extraction_results['relationships'])} relationships in Graphiti")
                        
                        # Log the entity map for debugging
                        logger.info(f"Entity ID map contents ({len(entity_id_map)} entities):")
                        for entity_name, entity_id in entity_id_map.items():
                            logger.info(f"  '{entity_name}' -> {entity_id}")
                        
                        # Skip map to avoid duplicate relationships
                        processed_rels = set()
                        
                        # Maximum relationships per file ingestion
                        relationship_count = 0
                        
                        # Sort relationships by sentence ID so we process related entities in same sentence first
                        sorted_relationships = sorted(extraction_results["relationships"], key=lambda r: r.get("sentence_id", 0))
                        
                        for rel in sorted_relationships:
                            # Stop if we've reached the maximum relationships
                            if relationship_count >= self.MAX_RELATIONSHIPS_TOTAL:
                                logger.info(f"Reached maximum relationship limit ({self.MAX_RELATIONSHIPS_TOTAL}), skipping remaining relationships")
                                break
                                
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
                            
                            # Log entity ID mapping for debugging
                            logger.info(f"Relationship {rel_key}: source_id={source_id}, target_id={target_id}")
                            
                            # If we have both IDs, create the relationship
                            if source_id and target_id:
                                try:
                                    # Check if this relationship already exists
                                    check_query = """
                                    MATCH (a)-[r]->(b)
                                    WHERE elementId(a) = $source_id AND elementId(b) = $target_id
                                    AND type(r) = $rel_type AND r.scope = $scope
                                    RETURN count(r) as rel_count
                                    """
                                    
                                    check_result = await self.graphiti_service.execute_cypher(
                                        check_query, 
                                        {
                                            "source_id": source_id,
                                            "target_id": target_id,
                                            "rel_type": rel_type,
                                            "scope": scope
                                        }
                                    )
                                    
                                    # Skip if relationship already exists
                                    if check_result and check_result[0]["rel_count"] > 0:
                                        logger.info(f"Relationship already exists: {rel_key}")
                                        continue
                                    
                                    rel_id = await self.graphiti_service.create_relationship(
                                        source_id=source_id,
                                        target_id=target_id,
                                        rel_type=rel_type,
                                        properties={
                                            "context": rel["context"][:255] if "context" in rel else "",
                                            "source_file": file_path,
                                            "user_id": user_id,
                                            "scope": scope,
                                            "owner_id": owner_id
                                        },
                                        scope=scope,
                                        owner_id=owner_id
                                    )
                                    
                                    processed_rels.add(rel_key)
                                    relationship_count += 1
                                    
                                    relationship_results.append({
                                        "relationship_id": rel_id,
                                        "source": source_text,
                                        "target": target_text,
                                        "type": rel_type,
                                        "scope": scope,
                                        "owner_id": owner_id
                                    })
                                except Exception as e:
                                    logger.error(f"Error creating relationship in Graphiti: {e}")
                            else:
                                # Log why relationship creation was skipped
                                if not source_id and not target_id:
                                    logger.info(f"Skipping relationship {rel_key}: Both source and target entities missing")
                                elif not source_id:
                                    logger.info(f"Skipping relationship {rel_key}: Source entity '{source_text}' not found")
                                elif not target_id:
                                    logger.info(f"Skipping relationship {rel_key}: Target entity '{target_text}' not found")
            else:
                graphiti_result = {"error": "No chunks were successfully stored in Mem0, skipping Graphiti"}
                logger.warning("No chunks were successfully stored in Mem0, skipping Graphiti")
        except Exception as e:
            logger.error(f"Error processing Graphiti operations: {e}")
            graphiti_result = {"error": str(e)}
        
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
            "embeddings": {
                "count": embedding_count
            },
            "graphiti_result": graphiti_result,
            "trait_extraction": trait_extraction_result if 'trait_extraction_result' in locals() else None,
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