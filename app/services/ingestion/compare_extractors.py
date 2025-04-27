#!/usr/bin/env python
"""
Script to compare entity extractors.

This script compares the output of the Gemini-based entity extractor with older implementations.
"""

import os
import sys
import json
import logging
from argparse import ArgumentParser
from typing import Dict, List, Any
import asyncio

# Add the parent directory to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

# Now we can import our modules
from app.services.ingestion.entity_extraction_gemini import EntityExtractor
from app.services.ingestion.entity_extraction_factory import get_entity_extractor
from app.core.config import settings

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def main():
    """Compare entity extractors."""
    parser = ArgumentParser(description="Compare entity extractors")
    parser.add_argument("text", help="Text to extract entities from")
    args = parser.parse_args()
    
    # Initialize extractors
    gemini_extractor = EntityExtractor(
        api_key=settings.GEMINI_API_KEY,
        min_confidence=0.6
    )
    factory_extractor = get_entity_extractor()
    
    logger.info("Extracting entities from: %s", args.text)
    
    # Process text with each extractor
    gemini_entities = gemini_extractor.extract_entities(args.text)
    factory_entities = factory_extractor.extract_entities(args.text)
    
    # Print results
    logger.info("=== Gemini extractor ===")
    logger.info("%s entities found", len(gemini_entities))
    print(json.dumps(gemini_entities, indent=2))
    
    logger.info("=== Factory extractor ===")
    logger.info("%s entities found", len(factory_entities))
    print(json.dumps(factory_entities, indent=2))
    
    
if __name__ == "__main__":
    asyncio.run(main()) 