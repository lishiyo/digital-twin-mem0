"""Unified extraction pipeline for entities, relationships, and traits with Graphiti integration."""

import logging
import os
import asyncio
from typing import Dict, List, Any, Optional, Tuple, Set

from app.services.ingestion.entity_extraction_factory import get_entity_extractor
from app.services.traits import TraitExtractionService
from app.services.graph import GraphitiService, ContentScope
from app.services.traits.service import TraitExtractionService, Trait

logger = logging.getLogger(__name__)

# Pipeline configuration flags
ENABLE_GRAPHITI_INGESTION = True # Controls whether to store data in Graphiti knowledge graph
ENABLE_PROFILE_UPDATES = True     # Controls whether to update user profiles with traits

# You can override these flags with environment variables
import os
if os.environ.get("ENABLE_GRAPHITI_INGESTION", "").lower() in ("false", "0", "no"):
    ENABLE_GRAPHITI_INGESTION = False
if os.environ.get("ENABLE_PROFILE_UPDATES", "").lower() in ("false", "0", "no"):
    ENABLE_PROFILE_UPDATES = False

logger.info(f"ExtractionPipeline config: ENABLE_GRAPHITI_INGESTION={ENABLE_GRAPHITI_INGESTION}, ENABLE_PROFILE_UPDATES={ENABLE_PROFILE_UPDATES}")

class ExtractionPipeline:
    """Unified extraction pipeline for entities, relationships, and traits with Graphiti integration."""
    
    # Confidence thresholds for adding to graph
    MIN_CONFIDENCE_ENTITY = 0.65
    MIN_CONFIDENCE_RELATIONSHIP = 0.6
    MIN_CONFIDENCE_TRAIT = 0.8
   
    # Limits on number of entities and relationships
    MAX_ENTITIES_PER_CHUNK = 20
    MAX_RELATIONSHIPS_TOTAL = 40
    
    # Mapping between trait types and node types in Graphiti
    TRAIT_TYPE_MAPPING = {
        "skill": "Skill",
        "interest": "Interest",
        "preference": "Preference",
        "dislike": "Dislike",
        "person": "Person",
        "attribute": "Attribute"
    }
    
    def __init__(self, entity_extractor=None, trait_service=None, graphiti_service=None):
        """Initialize the extraction pipeline.
        
        Args:
            entity_extractor: EntityExtractor instance
            trait_service: TraitExtractionService instance
            graphiti_service: GraphitiService instance
        """
        self.entity_extractor = entity_extractor or get_entity_extractor()
        self.trait_service = trait_service
        self.graphiti = graphiti_service or GraphitiService()
    
    async def extract_from_content(self, content, user_id, metadata, source_type="chat", 
                                  process_chunks=False, chunk_boundaries=None):
        """Extract entities, relationships, and traits from content.
        if ENABLE_GRAPHITI_INGESTION:
            This will extract entities, relationships, and traits
        if ENABLE_PROFILE_UPDATES:
            This will extract traits and update the user profile
        
        Args:
            content: Text content to process
            user_id: User ID
            metadata: Content metadata
            source_type: Source type ("chat" or "document")
            process_chunks: Whether to process in chunks
            chunk_boundaries: Optional chunk boundaries for documents
            
        Returns:
            Dictionary with extracted entities, relationships, and traits (as dictionaries)
        """
        if not self.trait_service:
            logger.warning("No TraitExtractionService provided, trait extraction will be skipped")
            
        extraction_results = {
            "entities": [],
            "relationships": [],
            "traits": []
        }
        
        # Skip entity and relationship extraction if Graphiti ingestion is disabled
        # and profile updates are enabled (we only need traits)
        extract_entities = ENABLE_GRAPHITI_INGESTION
        extract_traits = ENABLE_PROFILE_UPDATES or ENABLE_GRAPHITI_INGESTION
        
        if not extract_entities and not extract_traits:
            logger.info("Both Graphiti ingestion and profile updates are disabled. Nothing to do.")
            return extraction_results
            
        if process_chunks and chunk_boundaries:
            logger.info(f"extract_from_content: Processing content in chunks with {len(chunk_boundaries)} chunks")
            # Process each chunk separately
            all_entities = []
            all_relationships = []
            all_traits = [] # list of trait models
            
            for i, (start, end) in enumerate(chunk_boundaries):
                chunk_content = content[start:end]
                chunk_metadata = {**metadata, "chunk_index": i}
                
                # Process entities and relationships in this chunk (if needed)
                if extract_entities:
                    entity_results = self.entity_extractor.process_document(chunk_content)
                    logger.info(f"extract_from_content: Extracted {len(entity_results.get('entities', []))} entities and {len(entity_results.get('relationships', []))} relationships from chunk {i}")
                    
                    # Update start/end positions to match original document
                    for entity in entity_results.get("entities", []):
                        entity["start"] += start
                        entity["end"] += start
                        entity["chunk_index"] = i
                    
                    all_entities.extend(entity_results.get("entities", []))
                    all_relationships.extend(entity_results.get("relationships", []))
                
                # Extract traits for each chunk if needed
                if extract_traits and self.trait_service:
                    try:
                        chunk_trait_result = await self.trait_service.extract_traits(
                            content=chunk_content,
                            source_type=source_type,
                            user_id=user_id,
                            metadata=chunk_metadata,
                            update_profile=False  # Don't update profile yet, we'll do it explicitly
                        )
                        logger.info(f"extract_from_content: Extracted {len(chunk_trait_result.get('traits', []))} traits from chunk {i}")
                        # IMPORTANT: we are grabbing the trait MODELS here, not the trait dictionaries
                        all_traits.extend(chunk_trait_result.get("trait_models", []))
                    except Exception as e:
                        logger.error(f"extract_from_content: Error extracting traits from chunk {i}: {e}")
            
            # Combine results for the chunks
            if extract_entities:
                # Only add entities and relationships if we're extracting them for Graphiti
                extraction_results["entities"] = all_entities
                extraction_results["relationships"] = all_relationships
            
            # Deduplicate traits across chunks
            if all_traits:
                unique_traits = {}
                for trait in all_traits:
                    key = f"{trait.trait_type}:{trait.name}"
                    if key not in unique_traits or trait.confidence > unique_traits[key].confidence:
                        unique_traits[key] = trait
                
                # IMPORTANT: these must be trait MODELs, not dictionaries to pass to _update_user_profile
                extraction_results["traits"] = list(unique_traits.values())
                
                # Update user profile with combined traits if enabled
                if ENABLE_PROFILE_UPDATES and self.trait_service:
                    try:
                        logger.info(f"extract_from_content: Updating user profile with {len(extraction_results['traits'])} traits")
                        
                        # Update user profile with the trait MODELS
                        await self.trait_service._update_user_profile(user_id, extraction_results["traits"])
                    except Exception as e:
                        logger.error(f"extract_from_content: Error updating user profile with traits: {e}")
                        # Continue with other processing
                
                # Now we can reconvert back to the trait dictionaries
                extraction_results["traits"] = [trait.to_dict() for trait in extraction_results["traits"]]
        else:
            logger.info(f"extract_from_content: Processing entire content at once")
            
            if extract_entities:
                # Process entire content at once for entities and relationships if we're storing in Graphiti
                entity_results = self.entity_extractor.process_document(content)
                extraction_results["entities"] = entity_results.get("entities", [])
                extraction_results["relationships"] = entity_results.get("relationships", [])
            
            # Extract traits if needed
            if extract_traits and self.trait_service:
                try:
                    # For non-chunked content, just extract traits and let the service handle profile updates
                    # based on the configuration
                    trait_result = await self.trait_service.extract_traits(
                        content=content,
                        source_type=source_type,
                        user_id=user_id,
                        metadata=metadata,
                        update_profile=ENABLE_PROFILE_UPDATES  # Control with the global flag
                    )
                    
                    # Store trait dicts in results
                    extraction_results["traits"] = trait_result.get("traits", [])
                except Exception as e:
                    logger.error(f"extract_from_content: Error extracting traits: {e}")
        
        # Only apply entity and relationship limits if we're using them
        if extract_entities:
            extraction_results = self._apply_entity_relationship_limits(extraction_results)
        
        logger.info(f"extract_from_content FINAL: Extracted {len(extraction_results['entities'])} entities, {len(extraction_results['relationships'])} relationships, and {len(extraction_results['traits'])} traits")
        return extraction_results
    
    async def create_episode(self, content, user_id, title, metadata, scope="user", owner_id=None):
        """Create an episode in Graphiti. We create episodes for files first because each file
        represents a distinct information unit. Chat messages don't represent complete episodes.
        
        Args:
            content: Text content
            user_id: User ID
            title: Episode title
            metadata: Episode metadata
            scope: Content scope
            owner_id: Owner ID
            
        Returns:
            Dictionary with episode creation result
        """
        return await self.graphiti.add_episode(
            content=content[:500],  # Use a summary/preview of content
            user_id=user_id,
            metadata={
                "title": title,
                **metadata
            },
            scope=scope,
            owner_id=owner_id
        )
    
    async def process_extracted_data(self, extraction_results, user_id, source_id, 
                                    context_title=None, scope="user", owner_id=None, source="chat_message"):
        """Process extracted data and store in Graphiti.
        
        Args:
            extraction_results: Dictionary with extracted entities, relationships, and traits
            user_id: User ID
            source_id: Source ID (message_id or file_path)
            context_title: Optional context title (conversation or document title)
            scope: Content scope
            owner_id: Owner ID
            source: Source type ("chat_message" or "document")
            
        Returns:
            Dictionary with processing results as created entities, relationships, and traits
        """
        entities = extraction_results.get("entities", [])
        relationships = extraction_results.get("relationships", [])
        traits = extraction_results.get("traits", [])
        
        logger.info(f"process_extracted_data: Processing {len(entities)} entities, {len(relationships)} relationships, and {len(traits)} traits")
        
        # Results to track what was actually created
        created_entities = []
        created_relationships = []
        created_traits = []
        
        # Track created entity IDs by name for deduplication
        entity_map = {}
        
        # Determine if this is a chat or document source
        source_type = source
        logger.info(f"process_extracted_data: Source type is {source_type} from source_id: {source_id}")
        
        # Process entities
        for entity in entities:
            if entity.get("confidence", 0) < self.MIN_CONFIDENCE_ENTITY:
                logger.info(f"process_extracted_data: Skipping entity {entity.get('text', '')} because confidence is too low")
                continue
                
            entity_type = entity.get("entity_type", "Unknown")
            entity_name = entity.get("text", "").strip()
            
            if not entity_name or entity_name in entity_map:
                logger.info(f"process_extracted_data: Skipping entity {entity.get('text', '')} because it already exists")
                continue
                
            try:
                # Check if entity already exists in graph
                existing_entity = await self.graphiti.find_entity(
                    name=entity_name,
                    entity_type=entity_type,
                    scope=scope,
                    owner_id=owner_id
                )
                
                if existing_entity and existing_entity.get("id"):
                    # Entity already exists and has a valid ID, just store its ID
                    entity_map[entity_name] = existing_entity.get("id")
                    logger.info(f"process_extracted_data: Entity {entity_name} already exists with ID {existing_entity.get('id')}")
                    continue
                elif existing_entity:
                    # Entity exists but has no valid ID - log a warning and proceed to create it
                    logger.warning(f"process_extracted_data: Entity {entity_name} exists but has no valid ID. Creating a new instance.")

                # Create new entity
                entity_properties = {}
                
                # For Document entities, use "title" property instead of "name"
                if entity_type == "Document":
                    entity_properties["title"] = entity_name
                else:
                    entity_properties["name"] = entity_name
                    
                # Add common properties
                entity_properties["user_id"] = user_id
                entity_properties["source"] = source_type
                entity_properties["confidence"] = entity.get("confidence", 0.7)
                entity_properties["context"] = entity.get("context", "")
                
                # Add source-specific properties
                if source_type == "chat_message":
                    # For chat source, use message_id and conversation_title
                    entity_properties["message_id"] = source_id
                    entity_properties["conversation_title"] = context_title
                else:
                    # For document source, use source_id and context_title
                    entity_properties["source_id"] = source_id #file path
                    entity_properties["context_title"] = context_title
                
                entity_id = await self.graphiti.create_entity(
                    entity_type=entity_type,
                    properties=entity_properties,
                    scope=scope,
                    owner_id=owner_id
                )
                
                entity_map[entity_name] = entity_id
                created_entities.append({
                    "id": entity_id,
                    "name": entity_name,
                    "type": entity_type
                })
            except Exception as e:
                logger.error(f"process_extracted_data: Error handling entity {entity_name}: {str(e)}")
        
        # Process traits - disabled for now
        # for trait in traits:
        #     if trait.get("confidence", 0) < self.MIN_CONFIDENCE_TRAIT:
        #         logger.info(f"process_extracted_data: Skipping trait {trait.get('name', '')} because confidence is too low")
        #         continue
                
        #     trait_type = self.TRAIT_TYPE_MAPPING.get(
        #         trait.get("trait_type", "").lower(), 
        #         "Unknown"
        #     )
        #     trait_name = trait.get("name", "").strip()
            
        #     if not trait_name or trait_name in entity_map:
        #         continue
                
        #     try:
        #         # Check if trait already exists
        #         existing_trait = await self.graphiti.find_entity(
        #             name=trait_name,
        #             entity_type=trait_type,
        #             scope=scope,
        #             owner_id=owner_id
        #         )
                
        #         if existing_trait and existing_trait.get("id"):
        #             # Trait already exists and has a valid ID, just store its ID
        #             entity_map[trait_name] = existing_trait.get("id")
        #             logger.info(f"process_extracted_data: Trait {trait_name} already exists with ID {existing_trait.get('id')}")
        #             continue
        #         elif existing_trait:
        #             # Trait exists but has no valid ID - log a warning and proceed to create it
        #             logger.warning(f"process_extracted_data: Trait {trait_name} exists but has no valid ID. Creating a new instance.")
                    
        #         # Create new trait
        #         trait_properties = {
        #             "name": trait_name,
        #             "user_id": user_id,
        #             "source": source_type,
        #             "confidence": trait.get("confidence", 0.7),
        #             "strength": trait.get("strength", 0.7),
        #             "evidence": trait.get("evidence", "")
        #         }
                
        #         # Add source-specific properties
        #         if is_chat_source:
        #             # For chat source, use message_id and conversation_title
        #             trait_properties["message_id"] = source_id
        #             trait_properties["conversation_title"] = context_title
        #         else:
        #             # For document source, use source_id and context_title
        #             trait_properties["source_id"] = source_id
        #             trait_properties["context_title"] = context_title
                
        #         trait_id = await self.graphiti.create_entity(
        #             entity_type=trait_type,
        #             properties=trait_properties,
        #             scope=scope,
        #             owner_id=owner_id
        #         )
        #         logger.info(f"process_extracted_data: Created trait {trait_name} as entity in Graphiti with ID {trait_id}")
                
        #         entity_map[trait_name] = trait_id
        #         created_traits.append({
        #             "id": trait_id,
        #             "name": trait_name,
        #             "type": trait_type,
        #             "trait_type": trait.get("trait_type"),
        #             "confidence": trait.get("confidence", 0.7),
        #             "evidence": trait.get("evidence", ""),
        #             "strength": trait.get("strength", 0.7)
        #         })
        #     except Exception as e:
        #         logger.error(f"process_extracted_data: Error handling trait {trait_name}: {str(e)}")
        
        # Process relationships
        processed_relationships = set()
        
        for relationship in relationships:
            if relationship.get("confidence", 0) < self.MIN_CONFIDENCE_RELATIONSHIP:
                logger.info(f"process_extracted_data: Skipping relationship {relationship} because confidence is too low")
                continue
                
            source_name = relationship.get("source", "").strip()
            target_name = relationship.get("target", "").strip()
            rel_type = relationship.get("relationship", "MENTIONED_WITH")
            
            # Skip if source or target don't exist in our entity map
            if source_name not in entity_map or target_name not in entity_map:
                logger.info(f"process_extracted_data: Skipping relationship {relationship} because source or target doesn't exist in entity map")
                continue
                
            # Create a unique key for this relationship to avoid duplicates
            rel_key = f"{source_name}|{rel_type}|{target_name}"
            
            if rel_key in processed_relationships:
                logger.info(f"process_extracted_data: Skipping relationship {relationship} because it's a duplicate")
                continue
                
            processed_relationships.add(rel_key)
            
            try:
                # Check if relationship already exists
                relationship_exists = await self.graphiti.relationship_exists(
                    source_id=entity_map[source_name],
                    target_id=entity_map[target_name],
                    rel_type=rel_type,
                    scope=scope
                )
                
                if relationship_exists:
                    logger.info(f"process_extracted_data: Skipping relationship {relationship} because it already exists")
                    continue
                    
                # Create relationship between entities
                rel_properties = {
                    "user_id": user_id,
                    "confidence": relationship.get("confidence", 0.7),
                    "context": relationship.get("context", "")
                }
                
                # Add source-specific properties
                if source_type == "chat_message":
                    rel_properties["message_id"] = source_id
                else:
                    rel_properties["source_id"] = source_id
                
                rel_id = await self.graphiti.create_relationship(
                    source_id=entity_map[source_name],
                    target_id=entity_map[target_name],
                    rel_type=rel_type,
                    properties=rel_properties,
                    scope=scope,
                    owner_id=owner_id
                )
                
                created_relationships.append({
                    "id": rel_id,
                    "source": source_name,
                    "target": target_name,
                    "type": rel_type
                })
            except Exception as e:
                logger.error(f"process_extracted_data: Error creating relationship: {str(e)}")
        
        # Create relationships between traits and user
        # for trait in created_traits:
        #     trait_type = trait.get("trait_type")
        #     trait_id = trait.get("id")
            
        #     if not trait_type or not trait_id:
        #         continue
                
        #     # Different relationship types based on trait type
        #     rel_mapping = {
        #         "skill": "HAS_SKILL",
        #         "interest": "INTERESTED_IN",
        #         "preference": "PREFERS",
        #         "dislike": "DISLIKES",
        #         "attribute": "HAS_ATTRIBUTE"
        #     }
            
        #     rel_type = rel_mapping.get(trait_type.lower(), "ASSOCIATED_WITH")
            
        #     try:
        #         # Find user node
        #         user_entity = await self.graphiti.find_entity(
        #             name=user_id,  # Use user_id as name for user entity
        #             entity_type="Person",
        #             scope=scope,
        #             owner_id=owner_id
        #         )
                
        #         # Create user node if it doesn't exist
        #         if not user_entity:
        #             user_entity_id = await self.graphiti.create_entity(
        #                 entity_type="Person",
        #                 properties={
        #                     "name": user_id,
        #                     "user_id": user_id,
        #                     "source": "system"
        #                 },
        #                 scope=scope,
        #                 owner_id=owner_id
        #             )
        #             logger.info(f"process_extracted_data: Created user node for {user_id} with ID {user_entity_id}")
        #         else:
        #             logger.info(f"process_extracted_data: User node for {user_id} already exists with ID {user_entity.get('id')}")
        #             user_entity_id = user_entity.get("id")
                
        #         # Create relationship between user and trait
        #         rel_properties = {
        #             "user_id": user_id,
        #             "confidence": trait.get("confidence", 0.7),
        #             "strength": trait.get("strength", 0.7),
        #         }
                
        #         # Add source-specific properties
        #         if is_chat_source:
        #             rel_properties["message_id"] = source_id
        #         else:
        #             rel_properties["source_id"] = source_id
                
        #         rel_id = await self.graphiti.create_relationship(
        #             source_id=user_entity_id,
        #             target_id=trait_id,
        #             rel_type=rel_type,
        #             properties=rel_properties,
        #             scope=scope,
        #             owner_id=owner_id
        #         )
        #         logger.info(f"process_extracted_data: Created relationship between user {user_id} and trait {trait_id} with ID {rel_id}")
                
        #         created_relationships.append({
        #             "id": rel_id,
        #             "source": user_id,
        #             "target": trait.get("name"),
        #             "type": rel_type
        #         })
        #     except Exception as e:
        #         logger.error(f"process_extracted_data: Error creating user-trait relationship: {str(e)}")
    
        # Consolidate results
        return {
            "entities": created_entities,
            "relationships": created_relationships,
            "traits": created_traits
        }
    
    def process_extracted_data_sync(self, extraction_results, user_id, source_id, 
                                   context_title=None, scope="user", owner_id=None, source="chat_message"):
        """Synchronous version of process_extracted_data."""
        created_loop = False
        try:
            # Try to get an existing event loop
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                # No event loop in this thread, create one
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                created_loop = True
            
            # Run the async method to completion
            return loop.run_until_complete(
                self.process_extracted_data(extraction_results, user_id, source_id, context_title, scope, owner_id, source)
            )
        finally:
            # Clean up if we created a new loop
            if created_loop and loop:
                loop.close()
    
    async def process_document(self, content, user_id, file_path, metadata, 
                             chunk_boundaries=None, scope="user", owner_id=None):
        """Process a document by extracting entities, traits, and relationships and storing them in the DB
        
        Args:
            content (str): The content of the document
            user_id (str): The ID of the user who owns the document
            file_path (str): The path of the document
            metadata (dict): Additional metadata about the document
            chunk_boundaries (list): List of chunk boundaries for the document
            scope (str): The scope of the document (default: "user")
            owner_id (str): The ID of the owner of the document (default: None)
            
        Returns:
            Dictionary with episode_result, processing_result, extraction_results
        """
        # Create episode first
        episode_result = None
        if ENABLE_GRAPHITI_INGESTION:
            episode_result = await self.create_episode(
                content=content,
                user_id=user_id,
                title=metadata.get("title", os.path.basename(file_path)),
                metadata={
                    "source": "file",
                    "source_file": file_path,
                    **metadata
                },
                scope=scope,
                owner_id=owner_id
            )
            logger.info(f"1. Created episode {episode_result} for {file_path}")
        else:
            logger.info(f"1. Skipping episode creation for {file_path} because Graphiti ingestion is disabled")

        # Extract entities, relationships, and traits from content, using chunks if provided
        # This updates the user profile with the extracted traits
        # Depends on the flags for ENABLE_GRAPHITI_INGESTION and ENABLE_PROFILE_UPDATES
        extraction_results = await self.extract_from_content(
            content=content,
            user_id=user_id,
            metadata=metadata,
            source_type="document",
            process_chunks=bool(chunk_boundaries),
            chunk_boundaries=chunk_boundaries
        )
        logger.info(f"2. Extracted entities, relationships, and traits, updated profile: {extraction_results}")
        
        # Process extracted entities, relationships, and traits into Graphiti
        processing_result = None
        if ENABLE_GRAPHITI_INGESTION:   
            processing_result = await self.process_extracted_data(
                extraction_results,
                user_id,
                file_path,  # source_id
                metadata.get("title", os.path.basename(file_path)),  # context_title
                scope=scope,
                owner_id=owner_id,
                source="document"
            )
            logger.info(f"3. Processed extracted data into Graphiti: {processing_result}")
        else:   
            logger.info(f"3. Skipping Graphiti processing for {file_path} because Graphiti ingestion is disabled")
        
        return {
            "episode": episode_result,
            "processing": processing_result,
            "extraction": extraction_results
        }
    
    async def process_chat_message(self, message_content, user_id, message_id, 
                                 metadata, scope="user", owner_id=None):
        """Complete chat message processing pipeline.
        Depending on configuration, may store data in Graphiti and/or update user profile.
        
        Args:
            message_content: Message content
            user_id: User ID
            message_id: Message ID
            metadata: Message metadata
            scope: Content scope
            owner_id: Owner ID
            
        Returns:
            Dictionary with processing results and extraction results
            Processing results are the results of processing the extracted data into Graphiti, so will be empty if Graphiti ingestion is disabled.
            Extraction results are the results of the LLM extraction, which may include entities, relationships, and traits.
        """
        # Create result structure
        result = {
            "processing": {},
            "extraction": {}
        }
        
        # Extract content based on configuration
        # If Graphiti ingestion is enabled, this will extract entities, relationships, and traits and store in Graphiti
        # If profile updates are enabled, this will extract traits and update the user profile (but not store in Graphiti)
        extraction_results = await self.extract_from_content(
            content=message_content,
            user_id=user_id,
            metadata=metadata,
            source_type="chat",
            process_chunks=False  # Chat messages are typically short
        )
        
        if extraction_results.get("entities") or extraction_results.get("relationships") or extraction_results.get("traits"):
            logger.info(f"Extracted {len(extraction_results.get('entities', []))} entities, "
                      f"{len(extraction_results.get('relationships', []))} relationships, "
                      f"{len(extraction_results.get('traits', []))} traits from chat message")
            result["extraction"] = extraction_results
        
        # Process into Graphiti only if enabled
        if ENABLE_GRAPHITI_INGESTION and (extraction_results.get("entities") or 
                                        extraction_results.get("relationships") or 
                                        extraction_results.get("traits")):
            processing_result = await self.process_extracted_data(
                extraction_results,
                user_id,
                message_id,  # source_id
                metadata.get("conversation_title"),  # context_title
                scope=scope,
                owner_id=owner_id,
                source="chat_message"
            )
            logger.info(f"Processed chat data into Graphiti: {len(processing_result.get('entities', []))} entities, "
                      f"{len(processing_result.get('relationships', []))} relationships, "
                      f"{len(processing_result.get('traits', []))} traits")
            result["processing"] = processing_result
        elif not ENABLE_GRAPHITI_INGESTION:
            logger.info("Skipping Graphiti processing for chat message (Graphiti ingestion disabled)")
        
        return result
    
    def _apply_entity_relationship_limits(self, extraction_results):
        """Apply limits to the number of entities and relationships.
        
        Args:
            extraction_results: Dictionary with extracted entities, relationships, and traits
            
        Returns:
            Dictionary with filtered entities and relationships
        """
        entities = extraction_results.get("entities", [])
        relationships = extraction_results.get("relationships", [])
        
        # Group entities by chunk
        entities_by_chunk = {}
        for entity in entities:
            chunk_idx = entity.get("chunk_index", 0)  # Default to 0 if not set
            if chunk_idx not in entities_by_chunk:
                entities_by_chunk[chunk_idx] = []
            entities_by_chunk[chunk_idx].append(entity)
        
        # Apply entity limit per chunk
        filtered_entities = []
        for chunk_idx, chunk_entities in entities_by_chunk.items():
            # Sort entities by confidence first (highest confidence first), 
            # then by length (longest first) as a secondary criterion
            chunk_entities.sort(key=lambda e: (-e.get("confidence", 0), -len(e.get("text", ""))))
            
            # Take only up to MAX_ENTITIES_PER_CHUNK entities per chunk
            filtered_entities.extend(chunk_entities[:self.MAX_ENTITIES_PER_CHUNK])
            
            # Log how many entities were filtered out
            filtered_out = len(chunk_entities) - min(len(chunk_entities), self.MAX_ENTITIES_PER_CHUNK)
            if filtered_out > 0:
                logger.info(f"Filtered out {filtered_out} entities from chunk {chunk_idx} due to MAX_ENTITIES_PER_CHUNK limit")
        
        # Apply relationship limit for the entire document/message
        filtered_relationships = relationships
        if len(relationships) > self.MAX_RELATIONSHIPS_TOTAL:
            # Sort relationships by sentence ID so related entities in same sentence are prioritized
            filtered_relationships = sorted(relationships, key=lambda r: r.get("sentence_id", 0))[:self.MAX_RELATIONSHIPS_TOTAL]
            logger.info(f"Filtered out {len(relationships) - self.MAX_RELATIONSHIPS_TOTAL} relationships due to MAX_RELATIONSHIPS_TOTAL limit")
        
        # Return filtered results
        filtered_results = extraction_results.copy()
        filtered_results["entities"] = filtered_entities
        filtered_results["relationships"] = filtered_relationships
        
        return filtered_results 