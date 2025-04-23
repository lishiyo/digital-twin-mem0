"""Factory for entity extractors."""

import logging
from typing import Optional, Callable, Any

from app.core.config import settings
from app.services.ingestion.entity_extraction_gemini import EntityExtractor as GeminiEntityExtractor

logger = logging.getLogger(__name__)

# Try to import SpacyEntityExtractor for backward compatibility
try:
    from app.services.ingestion.entity_extraction import EntityExtractor as SpacyEntityExtractor
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False
    logger.warning("SpaCy entity extractor not available, falling back to Gemini only")

# Cache the entity extractor
_entity_extractor = None


def get_entity_extractor() -> GeminiEntityExtractor:
    """Get an entity extractor instance.
    
    Returns:
        EntityExtractor instance (using Gemini by default)
    """
    global _entity_extractor
    
    if _entity_extractor is None:
        logger.info("Creating new entity extractor")
        
        # Get API key
        api_key = settings.GEMINI_API_KEY
        if not api_key:
            logger.warning("GEMINI_API_KEY not set, entity extraction may not work correctly")
        
        # Create entity extractor
        _entity_extractor = GeminiEntityExtractor(
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
            extractor_type: Type of extractor to create ("spacy" or "gemini")
            **kwargs: Additional arguments to pass to the extractor constructor
            
        Returns:
            Entity extractor instance
        """
        # If no type specified, use the one from config
        if not extractor_type:
            extractor_type = settings.ENTITY_EXTRACTOR_TYPE
        
        extractor_type = extractor_type.lower()
        
        # Create appropriate extractor
        if extractor_type == "spacy" and SPACY_AVAILABLE:
            logger.info("Creating spaCy-based entity extractor")
            return SpacyEntityExtractor(**kwargs)
        elif extractor_type == "gemini":
            logger.info("Creating Gemini-based entity extractor")
            # Check if we have the required API key
            if not settings.GEMINI_API_KEY:
                logger.warning("GEMINI_API_KEY setting not provided in configuration")
                if SPACY_AVAILABLE:
                    logger.warning("Falling back to spaCy")
                    return SpacyEntityExtractor(**kwargs)
            
            # Pass the API key to the Gemini extractor
            return GeminiEntityExtractor(api_key=settings.GEMINI_API_KEY, **kwargs)
        else:
            logger.warning(f"Unknown extractor type: {extractor_type}, using Gemini")
            return get_entity_extractor() 