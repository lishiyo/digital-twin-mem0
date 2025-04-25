"""Service for extracting entities and traits from chat messages and storing them in Graphiti."""

from typing import Dict, List, Any, Optional, Tuple, Set
import logging
import json
from collections import defaultdict
import asyncio

from app.db.models.chat_message import ChatMessage, MessageRole
from app.db.models.conversation import Conversation
from app.db.models.user_profile import UserProfile
from app.services.graph import GraphitiService
from app.services.ingestion.entity_extraction_gemini import EntityExtractor
from app.services.traits import TraitExtractionService
from app.services.extraction_pipeline import ExtractionPipeline
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from app.db.models.user import User

logger = logging.getLogger(__name__)


class ChatGraphitiIngestion:
    """
        Service for extracting entities and traits from chat messages and storing them in Graphiti.
        This MUST be synchronous to work with Celery tasks.
    """
    

    def __init__(self, db_session: Session, graphiti_service: Optional[GraphitiService] = None, entity_extractor=None):
        """Initialize the service.
        
        Args:
            db_session: SQLAlchemy session
            graphiti_service: Optional GraphitiService instance
            entity_extractor: Optional EntityExtractor instance
        """
        self.db = db_session
        self.entity_extractor = entity_extractor or EntityExtractor()
        self.graphiti = graphiti_service or GraphitiService()
        self.trait_service = TraitExtractionService(db_session)
        
        # Create extraction pipeline
        self.extraction_pipeline = ExtractionPipeline(
            entity_extractor=self.entity_extractor,
            trait_service=self.trait_service,
            graphiti_service=self.graphiti
        )
    
    def process_message(self, message: ChatMessage) -> Dict[str, Any]:
        """Process a chat message and extract entities, relationships, and traits.
        
        Args:
            message: ChatMessage to process
            
        Returns:
            Dictionary with processing results
        """
        try:
            # Check if message was already processed
            if message.processed_in_graphiti:
                logger.info(f"Message {message.id} already processed for Graphiti, skipping")
                return {
                    "status": "skipped",
                    "message_id": message.id
                }
            
            # Skip assistant messages, we only want to process user messages
            if message.role == MessageRole.ASSISTANT:
                logger.info(f"Skipping assistant message {message.id}")
                message.processed_in_graphiti = True  # Mark as processed
                message.is_stored_in_graphiti = False  # But we didn't store anything
                self.db.commit()
                return {
                    "status": "skipped",
                    "reason": "assistant_message",
                    "message_id": message.id
                }
            
            # Skip if message is empty
            if not message.content or not message.content.strip():
                logger.info(f"Skipping empty message {message.id}")
                message.processed_in_graphiti = True  # Mark as processed
                message.is_stored_in_graphiti = False  # But we didn't store anything
                self.db.commit()
                return {
                    "status": "skipped",
                    "reason": "empty_message",
                    "message_id": message.id
                }
            
            # Get the conversation for context
            conversation = None
            if message.conversation_id:
                conversation_query = select(Conversation).where(Conversation.id == message.conversation_id)
                conversation_result = self.db.execute(conversation_query)
                conversation = conversation_result.scalar_one_or_none()
                
            # Get the user for user profile updates
            user_query = select(User).where(User.id == message.user_id).options(joinedload(User.profile))
            user_result = self.db.execute(user_query)
            user = user_result.scalar_one_or_none()
            
            if not user:
                logger.warning(f"User {message.user_id} not found, skipping profile updates")
                
            # Use asyncio.run to execute the async pipeline processing
            logger.info(f"Process_chat_message {message.id} with pipeline using asyncio.run")
            try:
                pipeline_result = asyncio.run(
                    self.extraction_pipeline.process_chat_message(
                        message_content=message.content,
                        user_id=message.user_id,
                        message_id=message.id,
                        metadata={
                            "message_id": message.id,
                            "conversation_title": conversation.title if conversation else None,
                            "conversation_id": message.conversation_id
                        },
                        scope="user",
                        owner_id=message.user_id
                    )
                )
            except RuntimeError as e:
                # Handle cases where asyncio.run cannot be used (e.g., nested event loops)
                # This might indicate a deeper issue, but provides a fallback/error path
                logger.error(f"Failed to run async pipeline for message {message.id} using asyncio.run: {e}. This might happen if called from an already running event loop.", exc_info=True)
                return {
                    "status": "error",
                    "reason": f"asyncio.run failed: {e}",
                    "message_id": message.id
                }
            
            # Get the processing results
            processing_result = pipeline_result.get("processing", {})
            
            # Skip processing if no entities or traits were found
            if not processing_result.get("entities", []) and not processing_result.get("traits", []):
                logger.info(f"Skipped storing {message.id} as no entities or traits were processed in Graphiti")
                message.processed_in_graphiti = True  # Mark as processed
                message.is_stored_in_graphiti = False  # But we didn't store anything
                self.db.commit()
                return {
                    "status": "skipped",
                    "reason": "no_entities_or_traits",
                    "message_id": message.id
                }
            
            # Mark message as processed
            message.processed_in_graphiti = True  # Always mark as processed

            # Only mark as stored if something was actually created
            entities_created = len(processing_result.get("entities", [])) > 0
            traits_created = len(processing_result.get("traits", [])) > 0
            message.is_stored_in_graphiti = entities_created or traits_created
            
            self.db.commit()
            
            logger.info(f"Successfully processed message {message.id} for Graphiti")
            return {
                "status": "success",
                "entities": processing_result.get("entities", []),
                "relationships": processing_result.get("relationships", []),
                "traits": processing_result.get("traits", []),
                "message_id": message.id
            }
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error processing message {message.id} for Graphiti: {str(e)}")
            return {
                "status": "error",
                "reason": str(e),
                "message_id": message.id
            }
    
    def process_pending_messages(self, limit: int = 50) -> Dict[str, Any]:
        """Process pending messages that haven't been processed through Graphiti.
        
        Args:
            limit: Maximum number of messages to process
            
        Returns:
            Dictionary with processing results
        """
        try:
            # Find unprocessed messages
            query = (
                select(ChatMessage)
                .where(ChatMessage.processed_in_graphiti == False)
                .limit(limit)
            )
            
            result = self.db.execute(query)
            messages = result.scalars().all()
            
            results = {
                "total": len(messages),
                "success": 0,
                "skipped": 0,
                "errors": 0,
                "details": []
            }
            
            # Process each message
            for message in messages:
                process_result = self.process_message(message)
                results["details"].append(process_result)
                
                if process_result["status"] == "success":
                    results["success"] += 1
                elif process_result["status"] == "skipped":
                    results["skipped"] += 1
                else:
                    results["errors"] += 1
            
            return results
            
        except Exception as e:
            logger.error(f"Error processing pending messages for Graphiti: {str(e)}")
            return {
                "status": "error",
                "reason": str(e),
                "total": 0,
                "success": 0,
                "skipped": 0,
                "errors": 0
            }
    
    def process_conversation(self, conversation_id: str) -> Dict[str, Any]:
        """Process all messages in a conversation for Graphiti.
        
        Args:
            conversation_id: ID of the conversation to process
            
        Returns:
            Dictionary with processing results
        """
        try:
            # Find unprocessed messages in the conversation
            query = (
                select(ChatMessage)
                .where(ChatMessage.conversation_id == conversation_id)
                .where(ChatMessage.processed_in_graphiti == False)
            )
            
            result = self.db.execute(query)
            messages = result.scalars().all()
            
            results = {
                "total": len(messages),
                "success": 0,
                "skipped": 0,
                "errors": 0,
                "conversation_id": conversation_id,
                "details": []
            }
            
            # Process each message
            for message in messages:
                process_result = self.process_message(message)
                results["details"].append(process_result)
                
                if process_result["status"] == "success":
                    results["success"] += 1
                elif process_result["status"] == "skipped":
                    results["skipped"] += 1
                else:
                    results["errors"] += 1
            
            return results
            
        except Exception as e:
            logger.error(f"Error processing conversation {conversation_id} for Graphiti: {str(e)}")
            return {
                "status": "error",
                "reason": str(e),
                "total": 0,
                "success": 0,
                "skipped": 0,
                "errors": 0,
                "conversation_id": conversation_id
            }
    
    # def _process_extracted_data(
    #     self, 
    #     extraction_results: Dict[str, Any], 
    #     user_id: str,
    #     message_id: str,
    #     conversation_title: Optional[str] = None
    # ) -> Dict[str, Any]:
    #     """Process extracted data and store in Graphiti.
        
    #     Args:
    #         extraction_results: Dictionary with extracted entities and traits
    #         user_id: ID of the user
    #         message_id: ID of the message
    #         conversation_title: Title of the conversation
            
    #     Returns:
    #         Dictionary with processing results
    #     """
    #     entities = extraction_results.get("entities", [])
    #     relationships = extraction_results.get("relationships", [])
    #     traits = extraction_results.get("traits", [])
        
    #     logger.info(f"Extracted entities: {entities}")
    #     logger.info(f"Extracted relationships: {relationships}")
    #     logger.info(f"Extracted traits: {traits}")
        
    #     # Results to track what was actually created
    #     created_entities = []
    #     created_relationships = []
    #     created_traits = []
        
    #     # Track created entity IDs by name for deduplication
    #     entity_map: Dict[str, str] = {}
        
    #     # Process entities
    #     for entity in entities:
    #         if entity.get("confidence", 0) < self.MIN_CONFIDENCE_ENTITY:
    #             continue
                
    #         entity_type = entity.get("entity_type", "Unknown")
    #         entity_name = entity.get("text", "").strip()
            
    #         if not entity_name or entity_name in entity_map:
    #             continue
                
    #         try:
    #             # Check if entity already exists in graph - use synchronous approach
    #             existing_entity = self.graphiti.find_entity_sync(
    #                 name=entity_name,
    #                 entity_type=entity_type,
    #                 scope="user",
    #                 owner_id=user_id
    #             )
                
    #             if existing_entity and existing_entity.get("id"):
    #                 # Entity already exists and has a valid ID, just store its ID
    #                 entity_map[entity_name] = existing_entity.get("id")
    #                 logger.info(f"Entity {entity_name} already exists in Graphiti with ID {existing_entity.get('id')}, skipping creation")
    #                 continue
    #             elif existing_entity:
    #                 # Entity exists but has no valid ID - log a warning and proceed to create it
    #                 logger.warning(f"Entity {entity_name} exists in Graphiti but has no valid ID. Creating a new instance.")

    #             # Create new entity - use synchronous approach
    #             entity_properties = {}
                
    #             # For Document entities, use "title" property instead of "name"
    #             if entity_type == "Document":
    #                 entity_properties["title"] = entity_name
    #             else:
    #                 entity_properties["name"] = entity_name
                    
    #             # Add other common properties
    #             entity_properties.update({
    #                 "user_id": user_id,
    #                 "source": "chat",
    #                 "confidence": entity.get("confidence", 0.7),
    #                 "context": entity.get("context", ""),
    #                 "message_id": message_id,
    #                 "conversation_title": conversation_title
    #             })
                
    #             entity_id = self.graphiti.create_entity_sync(
    #                 entity_type=entity_type,
    #                 properties=entity_properties,
    #                 scope="user",
    #                 owner_id=user_id
    #             )
                
    #             entity_map[entity_name] = entity_id
    #             created_entities.append({
    #                 "id": entity_id,
    #                 "name": entity_name,
    #                 "type": entity_type
    #             })
    #         except Exception as e:
    #             logger.error(f"Error handling entity {entity_name}: {str(e)}")
        
    #     # Process traits
    #     for trait in traits:
    #         if trait.get("confidence", 0) < self.MIN_CONFIDENCE_TRAIT:
    #             continue
                
    #         trait_type = self.TRAIT_TYPE_MAPPING.get(
    #             trait.get("trait_type", "").lower(), 
    #             "Unknown"
    #         )
    #         trait_name = trait.get("name", "").strip()
            
    #         if not trait_name or trait_name in entity_map:
    #             continue
                
    #         try:
    #             # Check if trait already exists - use synchronous approach
    #             existing_trait = self.graphiti.find_entity_sync(
    #                 name=trait_name,
    #                 entity_type=trait_type,
    #                 scope="user",
    #                 owner_id=user_id
    #             )
                
    #             if existing_trait and existing_trait.get("id"):
    #                 # Trait already exists and has a valid ID, just store its ID
    #                 entity_map[trait_name] = existing_trait.get("id")
    #                 logger.info(f"Trait {trait_name} already exists in Graphiti with ID {existing_trait.get('id')}, skipping creation")
    #                 continue
    #             elif existing_trait:
    #                 # Trait exists but has no valid ID - log a warning and proceed to create it
    #                 logger.warning(f"Trait {trait_name} exists in Graphiti but has no valid ID. Creating a new instance.")
                    
    #             # Create new trait - use synchronous approach
    #             trait_properties = {
    #                 "name": trait_name,
    #                 "user_id": user_id,
    #                 "source": "chat",
    #                 "confidence": trait.get("confidence", 0.7),
    #                 "strength": trait.get("strength", 0.7),
    #                 "evidence": trait.get("evidence", ""),
    #                 "message_id": message_id,
    #                 "conversation_title": conversation_title
    #             }
                
    #             trait_id = self.graphiti.create_entity_sync(
    #                 entity_type=trait_type,
    #                 properties=trait_properties,
    #                 scope="user",
    #                 owner_id=user_id
    #             )
                
    #             entity_map[trait_name] = trait_id
    #             created_traits.append({
    #                 "id": trait_id,
    #                 "name": trait_name,
    #                 "type": trait_type,
    #                 "trait_type": trait.get("trait_type"),
    #                 "confidence": trait.get("confidence", 0.7),
    #                 "evidence": trait.get("evidence", ""),
    #                 "strength": trait.get("strength", 0.7)
    #             })
    #         except Exception as e:
    #             logger.error(f"Error handling trait {trait_name}: {str(e)}")
        
    #     # Process relationships
    #     processed_relationships: Set[str] = set()
        
    #     for relationship in relationships:
    #         if relationship.get("confidence", 0) < self.MIN_CONFIDENCE_RELATIONSHIP:
    #             continue
                
    #         source_name = relationship.get("source", "").strip()
    #         target_name = relationship.get("target", "").strip()
    #         rel_type = relationship.get("relationship", "MENTIONED_WITH")
            
    #         # Skip if source or target don't exist in our entity map
    #         if source_name not in entity_map or target_name not in entity_map:
    #             continue
                
    #         # Create a unique key for this relationship to avoid duplicates
    #         rel_key = f"{source_name}|{rel_type}|{target_name}"
            
    #         if rel_key in processed_relationships:
    #             continue
                
    #         processed_relationships.add(rel_key)
            
    #         try:
    #             # Check if relationship already exists - use synchronous approach
    #             relationship_exists = self.graphiti.relationship_exists_sync(
    #                 source_id=entity_map[source_name],
    #                 target_id=entity_map[target_name],
    #                 rel_type=rel_type,
    #                 scope="user"
    #             )
                
    #             if relationship_exists:
    #                 continue
                    
    #             # Create relationship between entities
    #             rel_properties = {
    #                 "user_id": user_id,
    #                 "confidence": relationship.get("confidence", 0.7),
    #                 "context": relationship.get("context", ""),
    #                 "message_id": message_id
    #             }
                
    #             rel_id = self.graphiti.create_relationship_sync(
    #                 source_id=entity_map[source_name],
    #                 target_id=entity_map[target_name],
    #                 rel_type=rel_type,
    #                 properties=rel_properties,
    #                 scope="user",
    #                 owner_id=user_id
    #             )
                
    #             created_relationships.append({
    #                 "id": rel_id,
    #                 "source": source_name,
    #                 "target": target_name,
    #                 "type": rel_type
    #             })
    #         except Exception as e:
    #             logger.error(f"Error creating relationship: {str(e)}")
        
    #     # Create relationships between traits and user
    #     for trait in created_traits:
    #         trait_type = trait.get("trait_type")
    #         trait_id = trait.get("id")
            
    #         if not trait_type or not trait_id:
    #             continue
                
    #         # Different relationship types based on trait type
    #         rel_mapping = {
    #             "skill": "HAS_SKILL",
    #             "interest": "INTERESTED_IN",
    #             "preference": "PREFERS",
    #             "dislike": "DISLIKES",
    #             "attribute": "HAS_ATTRIBUTE"
    #         }
            
    #         rel_type = rel_mapping.get(trait_type.lower(), "ASSOCIATED_WITH")
            
    #         try:
    #             # Find user node - use synchronous approach
    #             user_entity = self.graphiti.find_entity_sync(
    #                 name=user_id,  # Use user_id as name for user entity
    #                 entity_type="Person",
    #                 scope="user",
    #                 owner_id=user_id
    #             )
                
    #             # Create user node if it doesn't exist - use synchronous approach
    #             if not user_entity:
    #                 user_entity_id = self.graphiti.create_entity_sync(
    #                     entity_type="Person",
    #                     properties={
    #                         "name": user_id,
    #                         "user_id": user_id,
    #                         "source": "system"
    #                     },
    #                     scope="user",
    #                     owner_id=user_id
    #                 )
    #             else:
    #                 user_entity_id = user_entity.get("id")
                
    #             # Create relationship between user and trait - use synchronous approach
    #             rel_properties = {
    #                 "user_id": user_id,
    #                 "confidence": trait.get("confidence", 0.7),
    #                 "strength": trait.get("strength", 0.7),
    #                 "message_id": message_id
    #             }
                
    #             rel_id = self.graphiti.create_relationship_sync(
    #                 source_id=user_entity_id,
    #                 target_id=trait_id,
    #                 rel_type=rel_type,
    #                 properties=rel_properties,
    #                 scope="user",
    #                 owner_id=user_id
    #             )
                
    #             created_relationships.append({
    #                 "id": rel_id,
    #                 "source": user_id,
    #                 "target": trait.get("name"),
    #                 "type": rel_type
    #             })
    #         except Exception as e:
    #             logger.error(f"Error creating user-trait relationship: {str(e)}")
        
    #     return {
    #         "entities": created_entities,
    #         "relationships": created_relationships,
    #         "traits": created_traits
    #     }
    