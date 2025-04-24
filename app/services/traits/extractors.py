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
            "metadata": self.metadata
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
            # Use the existing Gemini-based trait extraction
            raw_traits = self.entity_extractor.extract_traits(content)
            
            # Convert to our Trait objects
            traits = []
            for trait_dict in raw_traits:
                trait = self._gemini_trait_to_trait(
                    trait_dict,
                    {
                        "source": "chat",
                        "source_id": metadata.get("message_id"),
                        "context": metadata.get("conversation_title"),
                        "user_id": metadata.get("user_id")
                    }
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
        if not content or not content.strip():
            return []
        
        try:
            # Get extracted traits from the entity extractor
            extraction_results = self.entity_extractor.process_document(content)
            raw_traits = extraction_results.get("traits", [])
            
            # Convert to our Trait objects
            traits = []
            for trait_dict in raw_traits:
                trait = self._gemini_trait_to_trait(
                    trait_dict,
                    {
                        "source": "document",
                        "source_id": metadata.get("file_path"),
                        "context": metadata.get("title"),
                        "user_id": metadata.get("user_id"),
                        "file_metadata": {k: v for k, v in metadata.items() if k not in ["user_id", "file_path", "title"]}
                    }
                )
                traits.append(trait)
            
            return traits
            
        except Exception as e:
            logger.error(f"Error extracting traits from document: {str(e)}")
            return [] 