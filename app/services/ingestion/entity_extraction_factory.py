"""Factory for entity extractors."""

import logging
from typing import Optional, Callable, Any

from app.core.config import settings
from app.services.ingestion.entity_extraction_gemini import EntityExtractor

logger = logging.getLogger(__name__)

# Cache the entity extractor
_entity_extractor = None


def get_entity_extractor() -> EntityExtractor:
    """Get an entity extractor instance.
    
    Returns:
        EntityExtractor instance (using Gemini)
    """
    global _entity_extractor
    
    if _entity_extractor is None:
        logger.info("Creating new entity extractor")
        
        # Get API key
        api_key = settings.GEMINI_API_KEY
        if not api_key:
            logger.warning("GEMINI_API_KEY not set, entity extraction may not work correctly")
        
        # Create entity extractor
        _entity_extractor = EntityExtractor(
            api_key=api_key,
            min_confidence=0.6  # Default confidence threshold
        )
    
    return _entity_extractor


# For backward compatibility
class EntityExtractorFactory:
    """Factory for creating entity extractors."""
    
    @staticmethod
    def create_entity_extractor(extractor_type: Optional[str] = None, **kwargs) -> Any:
        """Create an entity extractor.
        
        Args:
            extractor_type: Type of extractor to create (only "gemini" is supported now)
            **kwargs: Additional arguments to pass to the extractor constructor
            
        Returns:
            Entity extractor instance
        """
        # Warn if requesting a type other than Gemini
        if extractor_type and extractor_type.lower() != "gemini":
            logger.warning(f"Extractor type '{extractor_type}' is not supported, using Gemini instead")
        
        # Check if we have the required API key
        if not settings.GEMINI_API_KEY:
            logger.error("GEMINI_API_KEY setting not provided in configuration")
            raise ValueError("GEMINI_API_KEY is required for entity extraction")
        
        # Return the cached extractor or create a new one
        return get_entity_extractor() 