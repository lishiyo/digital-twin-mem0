"""Factory for creating entity extractors."""

import os
import logging
from typing import Dict, Any, Optional

# Import both extractors
from app.services.ingestion.entity_extraction import EntityExtractor as SpacyEntityExtractor
from app.services.ingestion.entity_extraction_gemini import EntityExtractor as GeminiEntityExtractor
from app.core.config import settings

logger = logging.getLogger(__name__)

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
        if extractor_type == "spacy":
            logger.info("Creating spaCy-based entity extractor")
            return SpacyEntityExtractor(**kwargs)
        elif extractor_type == "gemini":
            logger.info("Creating Gemini-based entity extractor")
            # Check if we have the required API key
            if not settings.GEMINI_API_KEY:
                logger.warning("GEMINI_API_KEY setting not provided in configuration, falling back to spaCy")
                return SpacyEntityExtractor(**kwargs)
            
            # Pass the API key to the Gemini extractor
            return GeminiEntityExtractor(api_key=settings.GEMINI_API_KEY, **kwargs)
        else:
            logger.warning(f"Unknown extractor type: {extractor_type}, using spaCy")
            return SpacyEntityExtractor(**kwargs) 