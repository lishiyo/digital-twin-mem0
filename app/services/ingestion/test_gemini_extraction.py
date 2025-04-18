#!/usr/bin/env python
"""Test script for Gemini-based entity extraction."""

import os
import sys
import logging
import json
from dotenv import load_dotenv

# Add the project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import the entity extractors
from app.services.ingestion.entity_extraction import EntityExtractor as SpacyEntityExtractor
from app.services.ingestion.entity_extraction_gemini import EntityExtractor as GeminiEntityExtractor

def test_entity_extraction():
    """Compare SpaCy and Gemini entity extraction."""
    
    # Sample text
    text = """
    **Microsoft Azure** is a cloud computing platform created by Microsoft. It was launched in February 2010.
    John Smith, the CEO of Contoso, announced a partnership with Microsoft on January 15, 2023 in New York.
    The agreement will focus on developing new AI services for healthcare providers.
    """
    
    logger.info("Testing SpaCy entity extraction...")
    spacy_extractor = SpacyEntityExtractor()
    spacy_results = spacy_extractor.process_document(text)
    
    logger.info(f"SpaCy found {len(spacy_results['entities'])} entities, {len(spacy_results['relationships'])} relationships, and {len(spacy_results['keywords'])} keywords")
    
    try:
        logger.info("Testing Gemini entity extraction...")
        gemini_extractor = GeminiEntityExtractor()
        gemini_results = gemini_extractor.process_document(text)
        
        logger.info(f"Gemini found {len(gemini_results['entities'])} entities, {len(gemini_results['relationships'])} relationships, and {len(gemini_results['keywords'])} keywords")
        
        # Compare results
        logger.info("\nSpaCy entities:")
        for entity in spacy_results['entities']:
            logger.info(f"- {entity['text']} ({entity['entity_type']})")
        
        logger.info("\nGemini entities:")
        for entity in gemini_results['entities']:
            logger.info(f"- {entity['text']} ({entity['entity_type']})")
        
        logger.info("\nSpaCy relationships:")
        for rel in spacy_results['relationships']:
            logger.info(f"- {rel['source']} ({rel['source_type']}) -> {rel['relationship']} -> {rel['target']} ({rel['target_type']})")
        
        logger.info("\nGemini relationships:")
        for rel in gemini_results['relationships']:
            logger.info(f"- {rel['source']} ({rel['source_type']}) -> {rel['relationship']} -> {rel['target']} ({rel['target_type']})")
        
        logger.info("\nResults comparison successful!")
        return True
    
    except Exception as e:
        logger.error(f"Error testing Gemini extraction: {e}")
        return False

if __name__ == "__main__":
    logger.info("Starting entity extraction test")
    if test_entity_extraction():
        logger.info("Test completed successfully")
    else:
        logger.error("Test failed") 