"""Trait extractors for different data sources."""

from abc import ABC, abstractmethod
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

from app.services.ingestion.entity_extraction_factory import get_entity_extractor

logger = logging.getLogger(__name__)

class Trait:
    """Data class for a user trait."""
    
    def __init__(
        self,
        trait_type: str,
        name: str,
        confidence: float,
        evidence: str,
        source: str,
        source_id: Optional[str] = None,
        context: Optional[str] = None,
        strength: Optional[float] = None,
        extracted_at: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Initialize a trait.
        
        Args:
            trait_type: Type of trait (skill, interest, preference, dislike, attribute)
            name: Name of the trait
            confidence: Confidence score (0.0-1.0)
            evidence: Evidence text supporting the trait
            source: Source type (chat, document, etc.)
            source_id: Optional ID of the source (message_id, file_path, etc.)
            context: Optional additional context (conversation title, etc.)
            strength: Optional strength score (0.0-1.0)
            extracted_at: Optional timestamp of extraction
            metadata: Optional additional metadata
        """
        self.trait_type = trait_type
        self.name = name
        self.confidence = confidence
        self.evidence = evidence
        self.source = source
        self.source_id = source_id
        self.context = context
        self.strength = strength
        self.extracted_at = extracted_at or datetime.now()
        self.metadata = metadata or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert trait to dictionary for storage."""
        return {
            "trait_type": self.trait_type,
            "name": self.name,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "source": self.source,
            "source_id": self.source_id,
            "context": self.context,
            "strength": self.strength,
            "extracted_at": self.extracted_at.isoformat() if self.extracted_at else None,
        }


class TraitExtractor(ABC):
    """Base abstract trait extractor interface."""
    
    def __init__(self):
        """Initialize the extractor with a Gemini-based entity extractor."""
        self.entity_extractor = get_entity_extractor()
    
    @abstractmethod
    async def extract_traits(self, content: Any, metadata: Dict[str, Any]) -> List[Trait]:
        """Extract traits from content with associated metadata."""
        pass
    
    def _prepare_trait_metadata(self, trait_dict: Dict[str, Any], base_metadata: Dict[str, Any], source_type: str) -> Dict[str, Any]:
        """Prepare metadata for trait based on source type.
        
        Args:
            trait_dict: Raw trait dictionary from extraction
            base_metadata: Base metadata passed to the extractor
            source_type: Type of source ('chat' or 'document')
            
        Returns:
            Complete metadata dictionary for the trait
        """
        # Common metadata
        complete_metadata = {
            "user_id": base_metadata.get("user_id"),
            "source": source_type
        }
        
        # Add source-specific metadata
        if source_type == "chat":
            complete_metadata.update({
                "source_id": base_metadata.get("message_id"),
                "context": base_metadata.get("conversation_title"),
                "conversation_id": base_metadata.get("conversation_id"),
                "message_metadata": {k: v for k, v in base_metadata.items() 
                                   if k not in ["user_id", "message_id", "conversation_title", "conversation_id"]}
            })
        elif source_type == "document":
            complete_metadata.update({
                "source_id": base_metadata.get("file_path"),
                "context": base_metadata.get("title"),
                "file_metadata": {k: v for k, v in base_metadata.items() 
                                if k not in ["user_id", "file_path", "title"]}
            })
            
        return complete_metadata
    
    def _extract_traits_with_llm(self, content: str) -> List[Dict[str, Any]]:
        """Extract traits using the LLM.
        
        Args:
            content: Text content to analyze
            
        Returns:
            List of trait dictionaries with trait_type, name, confidence, evidence
        """
        if not content or not content.strip():
            return []
            
        try:
            # Ensure model is initialized
            self.entity_extractor._ensure_model_initialized()
            
            # Create prompt for trait extraction
            prompt = f"""
            Analyze the following text and extract important user traits. Focus on:
            1. Skills (things the user knows how to do)
            2. Interests (things the user likes or is curious about)
            3. Preferences (things the user prefers over alternatives)
            4. Dislikes (things the user specifically doesn't like)
            5. Attributes (facts about the user like relationships, possessions, characteristics)
            
            For each trait, provide:
            1. Trait type: One of these categories: "skill" (abilities/expertise), "interest" (likes/hobbies), 
               "preference" (things preferred), "dislike" (things disliked), "attribute" (background, personality, details about the user)
            2. Name: The full trait description (for example don't say "Name", say "name is Connie", "has a husband named Kyle", "lives in San Francisco")
            3. Evidence: The text that supports this trait (give full sentence if possible)
            4. Confidence: A number between 0.0 and 1.0 representing your confidence in this trait
            5. Strength: A number between 0.0 and 1.0 representing the strength of this trait (optional)
            
            Only extract traits that are clearly supported by the text. Ignore generic or very common traits unless they're emphasized.
            
            TEXT:
            {content[:4000]}  # Limit content length for LLM
            
            Return your answer as a JSON list of objects with the following properties:
            - trait_type: The trait type from the list above
            - name: The trait description ("name is Connie", "age is 35" etc)
            - evidence: The text that supports this trait
            - confidence: A confidence score between 0.0 and 1.0
            - strength: (Optional) A strength score between 0.0 and 1.0
            
            If no traits are found, return an empty list.
            """
            
            # Make API call to Gemini
            response = self.entity_extractor._model.generate_content(prompt)
            response_text = response.text
            
            # Try to extract JSON from response
            traits = self.entity_extractor._extract_json_from_response(response_text)
            
            logger.info(f"Extracted {len(traits)} traits using LLM")
            return traits
            
        except Exception as e:
            logger.error(f"Error extracting traits with LLM: {str(e)}")
            return []
    
    def _gemini_trait_to_trait(self, trait_dict: Dict[str, Any], metadata: Dict[str, Any]) -> Trait:
        """Convert a trait dictionary from Gemini to a Trait object."""
        source = metadata.get("source", "unknown")
        source_id = metadata.get("source_id")
        context = metadata.get("context")
        
        return Trait(
            trait_type=trait_dict.get("trait_type", "").lower(),
            name=trait_dict.get("name", ""),
            confidence=float(trait_dict.get("confidence", 0.0)),
            evidence=trait_dict.get("evidence", ""),
            source=source,
            source_id=source_id,
            context=context,
            strength=float(trait_dict.get("strength", 0.0)) if "strength" in trait_dict else None,
            metadata=metadata
        )


class ChatTraitExtractor(TraitExtractor):
    """Extracts traits from chat messages."""
    
    async def extract_traits(self, content: str, metadata: Dict[str, Any]) -> List[Trait]:
        """Extract traits from chat message content.
        
        Args:
            content: The chat message text
            metadata: Dictionary with message metadata
                Expected keys:
                - user_id: ID of the user
                - message_id: ID of the message
                - conversation_title: Optional title of the conversation
        
        Returns:
            List of extracted traits
        """
        if not content or not content.strip():
            return []
        
        try:
            # Use the trait extraction method defined in the base class
            raw_traits = self._extract_traits_with_llm(content)
            
            # Convert to our Trait objects
            traits = []
            for trait_dict in raw_traits:
                trait = self._gemini_trait_to_trait(
                    trait_dict,
                    self._prepare_trait_metadata(
                        trait_dict,
                        metadata,
                        "chat"
                    )
                )
                traits.append(trait)
            
            return traits
            
        except Exception as e:
            logger.error(f"Error extracting traits from chat: {str(e)}")
            return []


class DocumentTraitExtractor(TraitExtractor):
    """Extracts traits from documents."""
    
    async def extract_traits(self, content: str, metadata: Dict[str, Any]) -> List[Trait]:
        """Extract traits from document content.
        
        Args:
            content: The document text content
            metadata: Dictionary with document metadata
                Expected keys:
                - user_id: ID of the user
                - file_path: Path to the document
                - title: Optional document title
        
        Returns:
            List of extracted traits
        """
        logger.info(f"Extracting traits from document: {content[:100]}...")
        if not content or not content.strip():
            return []
        
        try:
            # Use the trait extraction method defined in the base class
            raw_traits = self._extract_traits_with_llm(content)
            
            # Convert to our Trait objects
            traits = []
            for trait_dict in raw_traits:
                trait = self._gemini_trait_to_trait(
                    trait_dict,
                    self._prepare_trait_metadata(
                        trait_dict,
                        metadata,
                        "document"
                    )
                )
                traits.append(trait)
            
            return traits
            
        except Exception as e:
            logger.error(f"Error extracting traits from document: {str(e)}")
            return [] 