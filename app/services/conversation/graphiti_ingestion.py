"""Service for extracting entities and traits from chat messages and storing them in Graphiti."""

from typing import Dict, List, Any, Optional, Tuple, Set
import logging
import json
from collections import defaultdict

from app.db.models.chat_message import ChatMessage, MessageRole
from app.db.models.conversation import Conversation
from app.db.models.user_profile import UserProfile
from app.services.graph import GraphitiService
from app.services.ingestion.entity_extraction_gemini import EntityExtractor
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from app.db.models.user import User

logger = logging.getLogger(__name__)


class ChatGraphitiIngestion:
    """Service for extracting entities and traits from chat messages and storing them in Graphiti."""
    
    # Mapping between extracted traits and their node types in Graphiti
    TRAIT_TYPE_MAPPING = {
        "skill": "Skill",
        "interest": "Interest",
        "preference": "Preference",
        "dislike": "Dislike",
        "person": "Person",
        "attribute": "Attribute"
    }
    
    # Confidence thresholds for adding to graph + user profile
    MIN_CONFIDENCE_ENTITY = 0.65
    MIN_CONFIDENCE_RELATIONSHIP = 0.6
    MIN_CONFIDENCE_TRAIT = 0.8
    MIN_CONFIDENCE_TRAIT_SKILL = 0.85
    MIN_CONFIDENCE_TRAIT_INTEREST = 0.85
    MIN_CONFIDENCE_TRAIT_PREFERENCE = 0.85
    MIN_CONFIDENCE_TRAIT_DISLIKE = 0.85
    MIN_CONFIDENCE_TRAIT_ATTRIBUTE = 0.85

    def __init__(
        self, 
        db_session: Session, 
        graphiti_service: Optional[GraphitiService] = None,
        entity_extractor: Optional[EntityExtractor] = None,
    ):
        """Initialize the service.
        
        Args:
            db_session: SQLAlchemy synchronous session
            graphiti_service: Service for interacting with Graphiti (created if None)
            entity_extractor: Service for extracting entities from text (created if None)
        """
        self.db = db_session
        self.graphiti = graphiti_service or GraphitiService()
        
        # Create entity extractor if not provided
        if entity_extractor is None:
            from app.services.ingestion.entity_extraction_factory import get_entity_extractor
            entity_extractor = get_entity_extractor()
        
        self.extractor = entity_extractor
    
    def should_ingest(self, message: ChatMessage) -> bool:
        """Determine if a message should be ingested into Graphiti.
        
        Args:
            message: ChatMessage to evaluate
            
        Returns:
            True if the message should be ingested, False otherwise
        """
        # Only ingest user messages, not assistant/twin messages
        return message.role == MessageRole.USER or message.role == MessageRole.SYSTEM
    
    def process_message(self, message: ChatMessage) -> Dict[str, Any]:
        """Process a chat message and extract entities, relationships, and traits.
        
        Args:
            message: The ChatMessage to process
            
        Returns:
            Dictionary with processing results
        """
        try:
            if message.processed_in_graphiti:
                logger.info(f"Message {message.id} already processed for Graphiti")
                return {
                    "status": "skipped",
                    "reason": "already_processed",
                    "message_id": message.id
                }
            
            # Skip assistant/twin messages
            if not self.should_ingest(message):
                logger.info(f"Message {message.id} with role {message.role} not ingested (assistant/twin messages are excluded)")
                # Mark as processed but not stored
                message.processed_in_graphiti = True
                message.is_stored_in_graphiti = False
                self.db.commit()
                return {
                    "status": "skipped",
                    "reason": "assistant_message_excluded",
                    "message_id": message.id
                }
            
            # Skip empty messages
            if not message.content or not message.content.strip():
                logger.info(f"Message {message.id} has no content, skipping Graphiti processing")
                message.processed_in_graphiti = True  # Mark as processed
                message.is_stored_in_graphiti = False  # Nothing was actually stored
                self.db.commit()
                return {
                    "status": "skipped",
                    "reason": "empty_content",
                    "message_id": message.id
                }
            
            # Get conversation for context
            query = select(Conversation).where(Conversation.id == message.conversation_id)
            result = self.db.execute(query)
            conversation = result.scalars().first()
            
            if not conversation:
                logger.error(f"Conversation {message.conversation_id} not found for message {message.id}")
                return {
                    "status": "error",
                    "reason": "conversation_not_found",
                    "message_id": message.id
                }
            
            # Get user profile (will be used to update with extracted traits)
            user_query = (
                select(User)
                .options(joinedload(User.profile))
                .where(User.id == message.user_id)
            )
            user_result = self.db.execute(user_query)
            user = user_result.scalars().first()
            
            if not user or not user.profile:
                logger.warning(f"User {message.user_id} or profile not found for message {message.id}")
            
            # Extract entities, relationships, and traits from message content
            extraction_results = self.extractor.process_document(message.content)
            
            # Skip processing if no entities or traits were found
            if (not extraction_results.get("entities") and not extraction_results.get("traits")) or \
               (len(extraction_results.get("entities", [])) == 0 and len(extraction_results.get("traits", [])) == 0):
                logger.info(f"Message {message.id} has no entities or traits, skipping Graphiti processing")
                message.processed_in_graphiti = True  # Mark as processed
                message.is_stored_in_graphiti = False  # Nothing was actually stored
                self.db.commit()
                return {
                    "status": "skipped",
                    "reason": "no_entities_or_traits",
                    "message_id": message.id
                }
            
            # Process extracted data
            processing_result = self._process_extracted_data(
                extraction_results, 
                message.user_id,
                message.id,
                conversation.title if conversation else None
            )
            
            # Update user profile if relevant traits were found
            if user and user.profile and processing_result.get("traits"):
                self._update_user_profile(user.profile, processing_result["traits"])
            
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
    
    def _process_extracted_data(
        self, 
        extraction_results: Dict[str, Any], 
        user_id: str,
        message_id: str,
        conversation_title: Optional[str] = None
    ) -> Dict[str, Any]:
        """Process extracted data and store in Graphiti.
        
        Args:
            extraction_results: Dictionary with extracted entities and traits
            user_id: ID of the user
            message_id: ID of the message
            conversation_title: Title of the conversation
            
        Returns:
            Dictionary with processing results
        """
        entities = extraction_results.get("entities", [])
        relationships = extraction_results.get("relationships", [])
        traits = extraction_results.get("traits", [])
        
        logger.info(f"Extracted entities: {entities}")
        logger.info(f"Extracted relationships: {relationships}")
        logger.info(f"Extracted traits: {traits}")
        
        # Results to track what was actually created
        created_entities = []
        created_relationships = []
        created_traits = []
        
        # Track created entity IDs by name for deduplication
        entity_map: Dict[str, str] = {}
        
        # Process entities
        for entity in entities:
            if entity.get("confidence", 0) < self.MIN_CONFIDENCE_ENTITY:
                continue
                
            entity_type = entity.get("entity_type", "Unknown")
            entity_name = entity.get("text", "").strip()
            
            if not entity_name or entity_name in entity_map:
                continue
                
            try:
                # Check if entity already exists in graph - use synchronous approach
                existing_entity = self.graphiti.find_entity_sync(
                    name=entity_name,
                    entity_type=entity_type,
                    scope="user",
                    owner_id=user_id
                )
                
                if existing_entity and existing_entity.get("id"):
                    # Entity already exists and has a valid ID, just store its ID
                    entity_map[entity_name] = existing_entity.get("id")
                    logger.info(f"Entity {entity_name} already exists in Graphiti with ID {existing_entity.get('id')}, skipping creation")
                    continue
                elif existing_entity:
                    # Entity exists but has no valid ID - log a warning and proceed to create it
                    logger.warning(f"Entity {entity_name} exists in Graphiti but has no valid ID. Creating a new instance.")

                # Create new entity - use synchronous approach
                entity_properties = {}
                
                # For Document entities, use "title" property instead of "name"
                if entity_type == "Document":
                    entity_properties["title"] = entity_name
                else:
                    entity_properties["name"] = entity_name
                    
                # Add other common properties
                entity_properties.update({
                    "user_id": user_id,
                    "source": "chat",
                    "confidence": entity.get("confidence", 0.7),
                    "context": entity.get("context", ""),
                    "message_id": message_id,
                    "conversation_title": conversation_title
                })
                
                entity_id = self.graphiti.create_entity_sync(
                    entity_type=entity_type,
                    properties=entity_properties,
                    scope="user",
                    owner_id=user_id
                )
                
                entity_map[entity_name] = entity_id
                created_entities.append({
                    "id": entity_id,
                    "name": entity_name,
                    "type": entity_type
                })
            except Exception as e:
                logger.error(f"Error handling entity {entity_name}: {str(e)}")
        
        # Process traits
        for trait in traits:
            if trait.get("confidence", 0) < self.MIN_CONFIDENCE_TRAIT:
                continue
                
            trait_type = self.TRAIT_TYPE_MAPPING.get(
                trait.get("trait_type", "").lower(), 
                "Unknown"
            )
            trait_name = trait.get("name", "").strip()
            
            if not trait_name or trait_name in entity_map:
                continue
                
            try:
                # Check if trait already exists - use synchronous approach
                existing_trait = self.graphiti.find_entity_sync(
                    name=trait_name,
                    entity_type=trait_type,
                    scope="user",
                    owner_id=user_id
                )
                
                if existing_trait and existing_trait.get("id"):
                    # Trait already exists and has a valid ID, just store its ID
                    entity_map[trait_name] = existing_trait.get("id")
                    logger.info(f"Trait {trait_name} already exists in Graphiti with ID {existing_trait.get('id')}, skipping creation")
                    continue
                elif existing_trait:
                    # Trait exists but has no valid ID - log a warning and proceed to create it
                    logger.warning(f"Trait {trait_name} exists in Graphiti but has no valid ID. Creating a new instance.")
                    
                # Create new trait - use synchronous approach
                trait_properties = {
                    "name": trait_name,
                    "user_id": user_id,
                    "source": "chat",
                    "confidence": trait.get("confidence", 0.7),
                    "strength": trait.get("strength", 0.7),
                    "evidence": trait.get("evidence", ""),
                    "message_id": message_id,
                    "conversation_title": conversation_title
                }
                
                trait_id = self.graphiti.create_entity_sync(
                    entity_type=trait_type,
                    properties=trait_properties,
                    scope="user",
                    owner_id=user_id
                )
                
                entity_map[trait_name] = trait_id
                created_traits.append({
                    "id": trait_id,
                    "name": trait_name,
                    "type": trait_type,
                    "trait_type": trait.get("trait_type"),
                    "confidence": trait.get("confidence", 0.7)
                })
            except Exception as e:
                logger.error(f"Error handling trait {trait_name}: {str(e)}")
        
        # Process relationships
        processed_relationships: Set[str] = set()
        
        for relationship in relationships:
            if relationship.get("confidence", 0) < self.MIN_CONFIDENCE_RELATIONSHIP:
                continue
                
            source_name = relationship.get("source", "").strip()
            target_name = relationship.get("target", "").strip()
            rel_type = relationship.get("relationship", "MENTIONED_WITH")
            
            # Skip if source or target don't exist in our entity map
            if source_name not in entity_map or target_name not in entity_map:
                continue
                
            # Create a unique key for this relationship to avoid duplicates
            rel_key = f"{source_name}|{rel_type}|{target_name}"
            
            if rel_key in processed_relationships:
                continue
                
            processed_relationships.add(rel_key)
            
            try:
                # Check if relationship already exists - use synchronous approach
                relationship_exists = self.graphiti.relationship_exists_sync(
                    source_id=entity_map[source_name],
                    target_id=entity_map[target_name],
                    rel_type=rel_type,
                    scope="user"
                )
                
                if relationship_exists:
                    continue
                    
                # Create relationship between entities
                rel_properties = {
                    "user_id": user_id,
                    "confidence": relationship.get("confidence", 0.7),
                    "context": relationship.get("context", ""),
                    "message_id": message_id
                }
                
                rel_id = self.graphiti.create_relationship_sync(
                    source_id=entity_map[source_name],
                    target_id=entity_map[target_name],
                    rel_type=rel_type,
                    properties=rel_properties,
                    scope="user",
                    owner_id=user_id
                )
                
                created_relationships.append({
                    "id": rel_id,
                    "source": source_name,
                    "target": target_name,
                    "type": rel_type
                })
            except Exception as e:
                logger.error(f"Error creating relationship: {str(e)}")
        
        # Create relationships between traits and user
        for trait in created_traits:
            trait_type = trait.get("trait_type")
            trait_id = trait.get("id")
            
            if not trait_type or not trait_id:
                continue
                
            # Different relationship types based on trait type
            rel_mapping = {
                "skill": "HAS_SKILL",
                "interest": "INTERESTED_IN",
                "preference": "PREFERS",
                "dislike": "DISLIKES",
                "attribute": "HAS_ATTRIBUTE"
            }
            
            rel_type = rel_mapping.get(trait_type.lower(), "ASSOCIATED_WITH")
            
            try:
                # Find user node - use synchronous approach
                user_entity = self.graphiti.find_entity_sync(
                    name=user_id,  # Use user_id as name for user entity
                    entity_type="Person",
                    scope="user",
                    owner_id=user_id
                )
                
                # Create user node if it doesn't exist - use synchronous approach
                if not user_entity:
                    user_entity_id = self.graphiti.create_entity_sync(
                        entity_type="Person",
                        properties={
                            "name": user_id,
                            "user_id": user_id,
                            "source": "system"
                        },
                        scope="user",
                        owner_id=user_id
                    )
                else:
                    user_entity_id = user_entity.get("id")
                
                # Create relationship between user and trait - use synchronous approach
                rel_properties = {
                    "user_id": user_id,
                    "confidence": trait.get("confidence", 0.7),
                    "strength": trait.get("strength", 0.7),
                    "message_id": message_id
                }
                
                rel_id = self.graphiti.create_relationship_sync(
                    source_id=user_entity_id,
                    target_id=trait_id,
                    rel_type=rel_type,
                    properties=rel_properties,
                    scope="user",
                    owner_id=user_id
                )
                
                created_relationships.append({
                    "id": rel_id,
                    "source": user_id,
                    "target": trait.get("name"),
                    "type": rel_type
                })
            except Exception as e:
                logger.error(f"Error creating user-trait relationship: {str(e)}")
        
        return {
            "entities": created_entities,
            "relationships": created_relationships,
            "traits": created_traits
        }
    
    def _update_user_profile(self, profile: UserProfile, traits: List[Dict[str, Any]]) -> None:
        """Update user profile with extracted traits, handling confidence and conflicts.
        
        Args:
            profile: UserProfile to update
            traits: List of extracted traits
        """
        try:
            # Initialize profile sections if they don't exist or load from JSON
            skills = profile.skills if isinstance(profile.skills, list) else json.loads(profile.skills or '[]')
            interests = profile.interests if isinstance(profile.interests, list) else json.loads(profile.interests or '[]')
            preferences = profile.preferences if isinstance(profile.preferences, dict) else json.loads(profile.preferences or '{}')
            dislikes = profile.dislikes if isinstance(profile.dislikes, list) else json.loads(profile.dislikes or '[]')
            attributes = profile.attributes if isinstance(profile.attributes, list) else json.loads(profile.attributes or '[]')
            
            # Ensure profile fields are mutable lists/dicts for updates
            profile.skills = list(skills)
            profile.interests = list(interests)
            profile.preferences = dict(preferences)
            profile.dislikes = list(dislikes)
            profile.attributes = list(attributes)

            # Create maps of existing traits for deduplication and confidence checks
            # Store index along with data for easier update/removal
            skill_map = {s.get("name", "").lower(): (idx, s) for idx, s in enumerate(profile.skills) if isinstance(s, dict) and s.get("name")}
            interest_map = {i.get("name", "").lower(): (idx, i) for idx, i in enumerate(profile.interests) if isinstance(i, dict) and i.get("name")}
            preference_map = {}
            for category, prefs_dict in profile.preferences.items():
                if isinstance(prefs_dict, dict):
                    for name, details in prefs_dict.items():
                        if isinstance(details, dict):
                           preference_map[name.lower()] = (category, name, details) # Store category, original name, details
            dislike_map = {d.get("name", "").lower(): (idx, d) for idx, d in enumerate(profile.dislikes) if isinstance(d, dict) and d.get("name")}
            attribute_map = {a.get("name", "").lower(): (idx, a) for idx, a in enumerate(profile.attributes) if isinstance(a, dict) and a.get("name")}
            
            # Track staged additions (items not found in existing maps)
            staged_skills = []
            staged_interests = []
            staged_preferences = defaultdict(dict) # category -> {name: details}
            staged_dislikes = []
            staged_attributes = []

            # --- Step 1: Process incoming traits --- 
            for trait in traits:
                trait_type = trait.get("trait_type", "").lower()
                name = trait.get("name", "").strip()
                confidence = trait.get("confidence", 0.7)
                strength = trait.get("strength", 0.7) # Used for skill proficiency
                evidence = trait.get("evidence", "")
                
                logger.info(f"Processing trait: {trait} with confidence: {confidence}, strength: {strength}, name: {name}")
                if not name:
                    continue
                
                # Skip low confidence traits below the general threshold
                if confidence < self.MIN_CONFIDENCE_TRAIT:
                    logger.info(f"Skipping trait {name} with confidence {confidence} below threshold {self.MIN_CONFIDENCE_TRAIT}")
                    continue
                
                name_lower = name.lower()
                
                # Prepare the data structure for the trait
                trait_data = {
                    "name": name,
                    "confidence": confidence,
                    "source": "chat_inference",
                    "evidence": evidence
                }

                # Handle each trait type
                if trait_type == "skill" and confidence >= self.MIN_CONFIDENCE_TRAIT_SKILL:
                    trait_data["proficiency"] = strength
                    if name_lower in skill_map:
                        idx, existing_skill = skill_map[name_lower]
                        # Update existing only if new confidence is higher or equal
                        if confidence >= existing_skill.get("confidence", 0):
                            profile.skills[idx] = trait_data 
                            logger.info(f"Updating existing skill: {name}")
                    else:
                        # Stage trait for addition if it doesn't exist
                        staged_skills.append(trait_data)
                        
                elif trait_type == "interest" and confidence >= self.MIN_CONFIDENCE_TRAIT_INTEREST:
                    if name_lower in interest_map:
                        idx, existing_interest = interest_map[name_lower]
                        if confidence >= existing_interest.get("confidence", 0):
                            profile.interests[idx] = trait_data
                            logger.info(f"Updating existing interest: {name}")
                    else:
                        staged_interests.append(trait_data)
                        
                elif trait_type == "preference" and confidence >= self.MIN_CONFIDENCE_TRAIT_PREFERENCE:
                    category = "general" # Default category
                    if name_lower in preference_map:
                        orig_category, orig_name, existing_preference = preference_map[name_lower]
                        if confidence >= existing_preference.get("confidence", 0):
                            # Update directly in the profile's preference dict
                            profile.preferences[orig_category][orig_name] = trait_data
                            logger.info(f"Updating existing preference: {name} in category {orig_category}")
                    else:
                        # Stage new preference under its category
                        staged_preferences[category][name] = trait_data
                    
                elif trait_type == "dislike" and confidence >= self.MIN_CONFIDENCE_TRAIT_DISLIKE:
                    if name_lower in dislike_map:
                        idx, existing_dislike = dislike_map[name_lower]
                        if confidence >= existing_dislike.get("confidence", 0):
                            profile.dislikes[idx] = trait_data
                            logger.info(f"Updating existing dislike: {name}")
                    else:
                        staged_dislikes.append(trait_data)
                        
                elif trait_type == "attribute" and confidence >= self.MIN_CONFIDENCE_TRAIT_ATTRIBUTE:
                    if name_lower in attribute_map:
                        idx, existing_attribute = attribute_map[name_lower]
                        if confidence >= existing_attribute.get("confidence", 0):
                            profile.attributes[idx] = trait_data
                            logger.info(f"Updating existing attribute: {name}")
                    else:
                        staged_attributes.append(trait_data)
            
            # --- Step 2: Add staged new traits ---
            if staged_skills:
                profile.skills.extend(staged_skills)
                logger.info(f"Adding {len(staged_skills)} new skills")
            if staged_interests:
                profile.interests.extend(staged_interests)
                logger.info(f"Adding {len(staged_interests)} new interests")
            if staged_dislikes:
                profile.dislikes.extend(staged_dislikes)
                logger.info(f"Adding {len(staged_dislikes)} new dislikes")
            if staged_attributes:
                profile.attributes.extend(staged_attributes)
                logger.info(f"Adding {len(staged_attributes)} new attributes")
            
            # Merge staged preferences into the profile preferences dictionary
            if staged_preferences:
                for category, new_prefs in staged_preferences.items():
                    if category not in profile.preferences:
                        profile.preferences[category] = {}
                    profile.preferences[category].update(new_prefs)
                    logger.info(f"Adding {len(new_prefs)} new preferences to category '{category}'")

            # --- Step 3: Conflict Resolution between lists (Interest vs. Dislike) ---
            # Rebuild maps based on the potentially updated lists
            interest_map_final = {i.get("name", "").lower(): (idx, i) for idx, i in enumerate(profile.interests) if isinstance(i, dict) and i.get("name")}
            dislike_map_final = {d.get("name", "").lower(): (idx, d) for idx, d in enumerate(profile.dislikes) if isinstance(d, dict) and d.get("name")}
            
            conflicting_names = set(interest_map_final.keys()) & set(dislike_map_final.keys())
            
            # Keep track of indices to remove to avoid modifying list while iterating
            indices_to_remove_from_interests = set()
            indices_to_remove_from_dislikes = set()

            if conflicting_names:
                logger.warning(f"Found conflicts between interests and dislikes for: {conflicting_names}")
                
                for name_lower in conflicting_names:
                    interest_idx, interest_item = interest_map_final[name_lower]
                    dislike_idx, dislike_item = dislike_map_final[name_lower]
                    
                    # Keep the one with higher or equal confidence
                    if interest_item.get("confidence", 0) >= dislike_item.get("confidence", 0):
                        indices_to_remove_from_dislikes.add(dislike_idx)
                        logger.info(f"Resolving conflict for '{interest_item.get("name")}': Keeping interest, removing dislike.")
                    else:
                        indices_to_remove_from_interests.add(interest_idx)
                        logger.info(f"Resolving conflict for '{dislike_item.get("name")}': Keeping dislike, removing interest.")
                        
                # Filter out the lower confidence items using list comprehension with indices
                # Sort indices in reverse to avoid shifting issues during removal
                if indices_to_remove_from_interests:
                    profile.interests = [item for idx, item in enumerate(profile.interests) if idx not in indices_to_remove_from_interests]
                if indices_to_remove_from_dislikes:
                    profile.dislikes = [item for idx, item in enumerate(profile.dislikes) if idx not in indices_to_remove_from_dislikes]

            # --- Step 4: Commit Changes ---
            self.db.commit()
            logger.info(f"Updated user profile {profile.id} after processing traits.")
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating user profile {profile.id}: {str(e)}")
            