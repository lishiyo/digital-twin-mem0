"""Entity extraction utilities using Google's Gemini API."""

import logging
import os
from typing import Dict, List, Optional, Set, Tuple, Any
from collections import defaultdict
import re
import json

import google.generativeai as genai
from google.generativeai.types import GenerationConfig

from app.services.common.constants import (
    TRAIT_TYPE_TO_RELATIONSHIP_MAPPING, 
    RELATIONSHIP_TYPES,
    ENTITY_TYPE_MAPPING,
    IMPORTANT_ENTITY_TYPES
)

logger = logging.getLogger(__name__)

# Default Gemini model
DEFAULT_MODEL = "gemini-2.0-flash"

class EntityExtractor:
    """Class for extracting entities from text using Google's Gemini API."""
    
    _initialized = False
    _model = None
    
    def __init__(self, model_name: str = DEFAULT_MODEL, min_confidence: float = 0.6, api_key: Optional[str] = None):
        """Initialize the entity extractor.
        
        Args:
            model_name: Name of the Gemini model to use
            min_confidence: Minimum confidence threshold for entity filtering
            api_key: Google Gemini API key (if None, will try to get from environment)
        """
        self.model_name = model_name
        self.min_confidence = min_confidence
        self.api_key = api_key
        self._ensure_model_initialized()
    
    def _ensure_model_initialized(self) -> None:
        """Ensure the Gemini model is initialized."""
        if not self._initialized:
            # If no API key is provided directly, consider it a critical error
            if not self.api_key:
                raise ValueError("No Gemini API key provided. Please provide an API key.")
            
            try:
                logger.info(f"Initializing Gemini API with model: {self.model_name}")
                genai.configure(api_key=self.api_key)
                
                # Initialize the model
                self._model = genai.GenerativeModel(
                    model_name=self.model_name,
                    generation_config=GenerationConfig(
                        temperature=0.1,  # Low temperature for factual responses
                        top_p=0.9,
                        top_k=32,
                    )
                )
                self._initialized = True
                logger.info("Gemini API initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini API: {e}")
                raise
    
    def extract_entities(self, text: str, chunk_index: int = 0) -> List[Dict[str, Any]]:
        """Extract entities from text.
        
        Args:
            text: Text to extract entities from
            chunk_index: Index of the chunk this text belongs to
            
        Returns:
            List of extracted entities with details
        """
        if not text.strip():
            return []
        
        # Ensure model is initialized
        self._ensure_model_initialized()
        
        # Create prompt for entity extraction
        prompt = f"""
        Extract entities from the following text. For each entity, provide:
        1. The entity text
        2. The entity type (PERSON, ORG, GPE, LOC, PRODUCT, WORK_OF_ART, EVENT, DATE, TIME, MONEY, PERCENT, NORP, FAC, LAW, LANGUAGE, ORDINAL, CARDINAL, QUANTITY, NAMED_BEING (this is not a person but has a name, like animals)), or a trait like (ATTRIBUTE, INTEREST, SKILL, PREFERENCE, LIKE, DISLIKE))
        3. The start and end character positions in the text
        4. A confidence score between 0 and 1
        5. The surrounding context (a few words before and after)

       Regarding traits, extract attributes, interests, skills, preferences, likes and dislikes as entities:
        - ATTRIBUTE: Any descriptive quality (e.g., "tall", "fat", "red", "expensive")
        - INTEREST: Activities or topics someone enjoys or is curious about (e.g., "hiking", "movies", "AI")
        - SKILL: Abilities or competencies (e.g., "Python", "painting", "cooking")
        - PREFERENCE: Things someone prefers (e.g., "Italian food", "warm weather")
        - LIKE: Things someone likes or loves (e.g., "tuna", "hiking")
        - DISLIKE: Things someone dislikes (e.g., "cold weather", "mushrooms")

        For example, in "Mochi is fat and loves tuna", extract:
            - "Mochi" as PERSON
            - "fat" as ATTRIBUTE
            - "tuna" as LIKE

        Return your answer as a JSON list of objects with the following properties:
        - text: The entity text
        - label: The entity type from the list above
        - start: The start character position
        - end: The end character position
        - confidence: A confidence score between 0 and 1
        - context: The surrounding context

        IMPORTANT: ONLY include high-quality entities - ignore common words, formatting markers, anything not useful or relevant about the text's author. "I" should count as a person.
        If you detect text in bold (surrounded by ** characters), consider those as potential entities too.
        If you don't find any entities, return an empty JSON list.

        TEXT:
        {text}
        """
        
        try:
            # Make API call to Gemini - note: generate_content is not async
            response = self._model.generate_content(prompt)
            response_text = response.text
            
            # logger.info(f"Gemini response from entity extraction: {response_text}")
            
            # Try to extract JSON from response
            entities = self._extract_json_from_response(response_text)
            
            # If we couldn't extract JSON or got an empty list, try a different approach
            if not entities:
                logger.warning("Failed to extract entities JSON from Gemini response, retrying with structured prompt")
                return self._fallback_entity_extraction(text, chunk_index)
            
            # Post-process entities to match our expected format
            for entity in entities:
                # Set default values for any missing fields
                entity.setdefault("confidence", 0.8)
                entity.setdefault("start", 0)
                entity.setdefault("end", len(entity["text"]) if "text" in entity else 0)
                entity.setdefault("context", "")
                
                # Map entity type to our system type
                entity_type = ENTITY_TYPE_MAPPING.get(entity.get("label", ""), "Unknown")
                entity["entity_type"] = entity_type
                
                # Add sentence_id and chunk_index
                entity["sentence_id"] = 0  # Simplified, we don't track sentences
                entity["chunk_index"] = chunk_index
                
                # Filter low confidence entities
                if entity.get("confidence", 0) < self.min_confidence:
                    entities.remove(entity)
            
            return entities
        
        except Exception as e:
            logger.error(f"Error calling Gemini API for entity extraction: {e}")
            return self._fallback_entity_extraction(text, chunk_index)
    
    def _extract_json_from_response(self, response_text: str) -> List[Dict[str, Any]]:
        """Extract JSON from the Gemini response text.
        
        Args:
            response_text: Response text from Gemini
            
        Returns:
            List of entity dictionaries
        """
        # Try to find JSON in the response
        json_match = re.search(r'\[[\s\S]*\]|\{[\s\S]*\}', response_text)
        if json_match:
            try:
                entities = json.loads(json_match.group(0))
                if isinstance(entities, list):
                    return entities
                elif isinstance(entities, dict) and "entities" in entities:
                    return entities["entities"]
            except json.JSONDecodeError:
                logger.warning("Failed to parse JSON from response")
        
        # If no JSON found or parsing failed, return empty list
        return []
    
    def _fallback_entity_extraction(self, text: str, chunk_index: int = 0) -> List[Dict[str, Any]]:
        """Fallback method for entity extraction.
        
        Args:
            text: Text to extract entities from
            chunk_index: Index of the chunk this text belongs to
            
        Returns:
            List of extracted entities with details
        """
        # More structured prompt with explicit instructions
        prompt = f"""
        Analyze the following text and extract all useful named entities.
        
        TEXT: {text}
        
        Respond ONLY with a JSON array of entities. If you cannot find any entities, return an empty list. 
        If you do find any, each entity should have these exact fields:
        - text: The exact text of the entity
        - label: One of these categories: PERSON, ORG, GPE, LOC, PRODUCT, WORK_OF_ART, EVENT, DATE, TIME, MONEY, PERCENT
        - start: Approximate character position where the entity starts (integer)
        - end: Approximate character position where the entity ends (integer)
        - confidence: A number between 0 and 1 representing your confidence
        - context: A short phrase containing the entity

        Example response format:
        [
          {{
            "text": "John Smith",
            "label": "PERSON",
            "start": 10,
            "end": 20,
            "confidence": 0.95,
            "context": "meeting with John Smith tomorrow"
          }}
        ]
        """
        
        try:
            # Make API call to Gemini - generate_content is not async
            response = self._model.generate_content(prompt)
            response_text = response.text
            
            # Try to extract JSON from response
            entities = self._extract_json_from_response(response_text)
            
            # Post-process entities 
            for entity in entities:
                # Add our system entity type
                entity_type = ENTITY_TYPE_MAPPING.get(entity.get("label", ""), "Unknown")
                entity["entity_type"] = entity_type
                
                # Add sentence_id and chunk_index
                entity["sentence_id"] = 0
                entity["chunk_index"] = chunk_index
            
            return entities
        
        except Exception as e:
            logger.error(f"Error in fallback entity extraction: {e}")
            # Return empty list if all extraction methods fail
            return []
    
    def extract_relationships(self, text: str, entities: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
        """Extract potential relationships between entities.
        
        Args:
            text: Text to extract relationships from
            entities: Optional pre-extracted entities. If None, entities will be extracted from text.
            
        Returns:
            List of potential relationships
        """
        if not text.strip():
            return []
        
        # Ensure model is initialized
        self._ensure_model_initialized()
        
        # Use provided entities or extract them if not provided
        if entities is None:
            entities = self.extract_entities(text)
        
        if len(entities) < 1:
            logger.warning(f"Not enough entities found for relationship extraction: {entities}")
            return []  # Some entities might be traits?
        
        # Create list of valid relationship types for the prompt, including trait types
        # Added trait relationship types
        rel_types = RELATIONSHIP_TYPES
        rel_types_str = ", ".join([f'"{rel_type}"' for rel_type in rel_types])
        
        # Create prompt for relationship extraction
        entity_mentions = ", ".join([f"{e['text']} ({e['entity_type']})" for e in entities])
        
        prompt = f"""
        Analyze the following text and identify relationships between these entities: {entity_mentions}
        
        TEXT:
        {text}
        
        Return a JSON list of relationships with the following properties:
        - source: The source entity text
        - source_type: The source entity type
        - target: The target entity text
        - target_type: The target entity type
        - relationship: The type of relationship - MUST be one of: {rel_types_str}
        - context: The text that contains both entities and describes their relationship
        - confidence: A number between 0 and 1 representing your confidence in the relationship
        - fact: A natural language description of the relationship (e.g., "John works at Microsoft", "Google is based in Mountain View")
        
        Guidelines for selecting relationship types:
        - Person to Organization: ASSOCIATED_WITH, WORKS_FOR, FOUNDED
        - Organization to Person: HAS_MEMBER
        - Person to Person: RELATED_TO
        - Person to Location: LOCATED_IN
        - Organization to Location: BASED_IN
        - Person to Document: CREATED
        - Document to Person: CREATED_BY
        - Person to Event: PARTICIPATED_IN
        - Organization to Event: ORGANIZED
        - Event to Location: LOCATED_IN
        - Person to Product: ASSOCIATED_WITH
        - Organization to Product: PRODUCED
        - Product to Organization: PRODUCED_BY
        
        Guidelines for trait/attribute relationships:
        - Person to Attribute: HAS_ATTRIBUTE (e.g., "John is 35 years old", "Mary has brown hair")
        - Person to Number/Cardinal: HAS_ATTRIBUTE (e.g., "Kyle is 28")
        - Person to Interest: INTERESTED_IN (e.g., "Jane likes hiking")
        - Person to Skill: HAS_SKILL (e.g., "Bob knows Python")
        - Person to Preference: LIKES (e.g., "Mary loves Italian food")
        - Person to Dislike: DISLIKES (e.g., "Tom hates cold weather")
        
        For any pair without a relevant specific type, use "MISSING"
        
        IMPORTANT: Identify who traits and attributes belong to based on the text. If the text says "Kyle is 28", create a relationship from Kyle to 28, not from the assumed message sender.
        
        Only include relationships that are clearly supported by the text.
        """
        
        try:
            # Make API call to Gemini - generate_content is not async
            response = self._model.generate_content(prompt)
            response_text = response.text
            
            # Try to extract JSON from response
            relationships = self._extract_json_from_response(response_text)
            
            # If extraction failed, return empty list
            if not relationships:
                return []
            
            # Post-process relationships to ensure proper typing and defaults
            for rel in relationships:
                # Add sentence_id field to match original API
                rel.setdefault("sentence_id", 0)
                
                # Validate and possibly correct relationship type
                source_type = rel.get("source_type")
                target_type = rel.get("target_type")
                
                if source_type and target_type:
                    # Ensure relationship type is from our defined set
                    if rel.get("relationship") not in rel_types:
                        # Is the type just "MISSING"? Let's log it to see if we need to add more types
                        if rel.get("relationship") == "MISSING":
                            logger.warning(f"Missing relationship type for {source_type} and {target_type}")
                        
                        # Use our mapping function to determine the proper relationship, this will fallback to MENTIONED_WITH if no other type is found
                        rel["relationship"] = self._determine_relationship_type(source_type, target_type)
                else:
                    # If type information is missing, use default
                    rel["relationship"] = "MENTIONED_WITH"
            
            return relationships
        
        except Exception as e:
            logger.error(f"Error calling Gemini API for relationship extraction: {e}")
            return []
    
    def extract_keywords(self, text: str, top_n: int = 10) -> List[Dict[str, Any]]:
        """Extract important keywords from text.
        
        Args:
            text: Text to extract keywords from
            top_n: Maximum number of keywords to return
            
        Returns:
            List of keywords with relevance scores
        """
        if not text.strip():
            return []
        
        # Ensure model is initialized
        self._ensure_model_initialized()
        
        # Create prompt for keyword extraction
        prompt = f"""
        Extract the {top_n} most important keywords or phrases from the following text.
        For each keyword, provide a relevance score between 0 and 1.
        
        TEXT:
        {text}
        
        Return your answer as a JSON list of objects with the following properties:
        - text: The keyword or phrase
        - count: An estimate of how many times this concept appears (directly or indirectly)
        - relevance: A score between 0 and 1 indicating the importance of this keyword to the text
        
        Only include genuinely important keywords that represent key concepts in the text.
        """
        
        try:
            # Make API call to Gemini - generate_content is not async
            response = self._model.generate_content(prompt)
            response_text = response.text
            
            # Try to extract JSON from response
            keywords = self._extract_json_from_response(response_text)
            
            # If extraction failed or empty, return empty list
            if not keywords:
                return []
            
            # Limit to top_n
            return keywords[:top_n]
        
        except Exception as e:
            logger.error(f"Error calling Gemini API for keyword extraction: {e}")
            return []
    
    def process_document(self, content: str, chunk_boundaries: List[Tuple[int, int]] = None) -> Dict[str, Any]:
        """Process a document or chat message and extract entities, relationships, and keywords.
        
        Args:
            content: Piece of text - document, chat message
            chunk_boundaries: Optional list of chunk boundaries as (start, end) tuples
            
        Returns:
            Dictionary with extracted entities, relationships, and keywords
        """
        if not content:
            return {"entities": [], "relationships": [], "keywords": []}
            
        # Extract keywords from the entire document
        keywords = self.extract_keywords(content)
        
        if chunk_boundaries:
            # Process entities by chunk
            all_entities = []
            for i, (start, end) in enumerate(chunk_boundaries):
                chunk_content = content[start:end]
                chunk_entities = self.extract_entities(chunk_content, chunk_index=i)
                
                # Adjust start and end positions to the original document
                for entity in chunk_entities:
                    entity["start"] += start
                    entity["end"] += start
                
                all_entities.extend(chunk_entities)
            
            # Process relationships from the entire document
            all_relationships = self.extract_relationships(content, all_entities)
            # logger.info(f"process_document: Extracted relationships: {all_relationships}")
            
            return {
                "entities": all_entities,
                "relationships": all_relationships,
                "keywords": keywords
            }
        else:
            # Process the whole document as a single chunk
            entities = self.extract_entities(content)
            relationships = self.extract_relationships(content, entities)
            # logger.info(f"process_document: Extracted relationships: {relationships}")
            
            return {
                "entities": entities,
                "relationships": relationships,
                "keywords": keywords
            }
    
    def _determine_relationship_type(self, source_type: str, target_type: str) -> str:
        """Determine relationship type based on entity types.
        
        Args:
            source_type: Type of source entity
            target_type: Type of target entity
            
        Returns:
            Relationship type
        """
        # Map of common entity type pairs to relationship types
        relationship_map = {
            ("Person", "Organization"): "ASSOCIATED_WITH",
            ("Organization", "Person"): "HAS_MEMBER",
            ("Person", "Person"): "RELATED_TO",
            ("Person", "Location"): "LOCATED_IN",
            ("Organization", "Location"): "BASED_IN",
            ("Person", "Document"): "CREATED",
            ("Document", "Person"): "CREATED_BY",
            ("Person", "Event"): "PARTICIPATED_IN",
            ("Event", "Person"): "INVOLVED",
            ("Organization", "Event"): "ORGANIZED",
            ("Event", "Organization"): "ORGANIZED_BY",
            ("Event", "Location"): "LOCATED_IN",
            ("Person", "Date"): "ASSOCIATED_WITH",
            ("Event", "Date"): "OCCURRED_ON",
            ("Document", "Date"): "PUBLISHED_ON",
            ("Organization", "Document"): "PUBLISHED",
            ("Document", "Organization"): "PUBLISHED_BY",
            ("Person", "Product"): "ASSOCIATED_WITH",
            ("Organization", "Product"): "PRODUCED",
            ("Product", "Organization"): "PRODUCED_BY",
            # Added trait/attribute relationship mappings
            ("Person", "Cardinal"): "HAS_ATTRIBUTE",  # For age and numeric attributes
            ("Person", "Attribute"): "HAS_ATTRIBUTE",
            ("Person", "Interest"): "INTERESTED_IN",
            ("Person", "Skill"): "HAS_SKILL",
            ("Person", "Preference"): "LIKES",
            ("Person", "Dislike"): "DISLIKES",
            # Common entity types that should be treated as attributes
            ("Person", "Number"): "HAS_ATTRIBUTE",
            ("Person", "Quantity"): "HAS_ATTRIBUTE",
            ("Person", "Age"): "HAS_ATTRIBUTE",
            ("Person", "Date"): "HAS_ATTRIBUTE",  # For birthdays, etc.
        }
        
        # Get relationship type from map, or use default
        return relationship_map.get((source_type, target_type), "MENTIONED_WITH") 