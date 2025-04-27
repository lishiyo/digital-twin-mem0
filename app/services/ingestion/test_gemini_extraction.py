#!/usr/bin/env python
"""Test script for Gemini entity extraction."""

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
from app.core.config import settings

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Sample text for testing
SAMPLE_TEXT = """
**Microsoft Azure** is a cloud computing platform created by Microsoft. It was launched in February 2010.
John Smith, the CEO of Contoso, announced a partnership with Microsoft on January 15, 2023 in New York.
The agreement will focus on developing new AI services for healthcare providers.

The project will utilize Azure's machine learning capabilities to improve diagnostic accuracy.
Dr. Emily Chen, a leading researcher in medical AI, will lead the technical implementation.

Contoso plans to invest $50 million in this initiative over the next three years.
"""


async def main():
    """Test Gemini entity extraction."""
    parser = ArgumentParser(description="Test Gemini entity extraction")
    parser.add_argument("--text", help="Text to extract entities from", default=SAMPLE_TEXT)
    parser.add_argument("--entities", action="store_true", help="Extract entities")
    parser.add_argument("--relationships", action="store_true", help="Extract relationships")
    parser.add_argument("--full", action="store_true", help="Process full document")
    args = parser.parse_args()
    
    if not any([args.entities, args.relationships, args.full]):
        # Default to full processing if no specific options provided
        args.full = True
    
    # Initialize extractor
    api_key = settings.GEMINI_API_KEY
    if not api_key:
        logger.error("GEMINI_API_KEY not set. Please set this environment variable.")
        sys.exit(1)
        
    extractor = EntityExtractor(api_key=api_key)
    
    # Process according to selected options
    if args.entities or args.full:
        logger.info("Extracting entities...")
        entities = extractor.extract_entities(args.text)
        logger.info(f"Found {len(entities)} entities")
        print(json.dumps(entities, indent=2))
    
    if args.relationships or args.full:
        logger.info("Extracting relationships...")
        relationships = extractor.extract_relationships(args.text)
        logger.info(f"Found {len(relationships)} relationships")
        print(json.dumps(relationships, indent=2))
    
    if args.full:
        logger.info("Processing full document...")
        result = extractor.process_document(args.text)
        logger.info(f"Found {len(result['entities'])} entities, {len(result['relationships'])} relationships")
        # Don't print the full result as it's already shown in parts


if __name__ == "__main__":
    asyncio.run(main()) 