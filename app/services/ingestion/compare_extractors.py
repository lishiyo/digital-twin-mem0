#!/usr/bin/env python
"""Compare spaCy and Gemini entity extraction side by side."""

import os
import sys
import logging
import json
import argparse
from dotenv import load_dotenv
from typing import Dict, List, Any

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

def extract_and_compare(text: str, output_format: str = "text") -> Dict[str, Any]:
    """Extract entities using both methods and compare results.
    
    Args:
        text: Text to extract entities from
        output_format: Output format ("text" or "json")
        
    Returns:
        Dictionary with comparison results
    """
    logger.info("Testing spaCy entity extraction...")
    spacy_extractor = SpacyEntityExtractor()
    spacy_results = spacy_extractor.process_document(text)
    
    logger.info(f"SpaCy found {len(spacy_results['entities'])} entities, {len(spacy_results['relationships'])} relationships, and {len(spacy_results['keywords'])} keywords")
    
    try:
        logger.info("Testing Gemini entity extraction...")
        gemini_extractor = GeminiEntityExtractor()
        gemini_results = gemini_extractor.process_document(text)
        
        logger.info(f"Gemini found {len(gemini_results['entities'])} entities, {len(gemini_results['relationships'])} relationships, and {len(gemini_results['keywords'])} keywords")
        
        # Prepare comparison results
        comparison = {
            "spacy": {
                "entities": spacy_results['entities'],
                "relationships": spacy_results['relationships'],
                "keywords": spacy_results['keywords'],
                "entity_count": len(spacy_results['entities']),
                "relationship_count": len(spacy_results['relationships']),
                "keyword_count": len(spacy_results['keywords'])
            },
            "gemini": {
                "entities": gemini_results['entities'],
                "relationships": gemini_results['relationships'],
                "keywords": gemini_results['keywords'],
                "entity_count": len(gemini_results['entities']),
                "relationship_count": len(gemini_results['relationships']),
                "keyword_count": len(gemini_results['keywords'])
            }
        }
        
        # Calculate unique entities in each
        spacy_entity_texts = {e['text'].lower() for e in spacy_results['entities']}
        gemini_entity_texts = {e['text'].lower() for e in gemini_results['entities']}
        
        # Find overlapping and unique entities
        common_entities = spacy_entity_texts.intersection(gemini_entity_texts)
        spacy_only = spacy_entity_texts - gemini_entity_texts
        gemini_only = gemini_entity_texts - spacy_entity_texts
        
        comparison["overlap"] = {
            "common_entity_count": len(common_entities),
            "spacy_only_count": len(spacy_only),
            "gemini_only_count": len(gemini_only),
            "common_entities": list(common_entities),
            "spacy_only": list(spacy_only),
            "gemini_only": list(gemini_only),
        }
        
        # Print results based on format
        if output_format == "json":
            print(json.dumps(comparison, indent=2))
        else:
            print("\n=== Entity Extraction Comparison ===")
            print(f"SpaCy: {comparison['spacy']['entity_count']} entities, {comparison['spacy']['relationship_count']} relationships, {comparison['spacy']['keyword_count']} keywords")
            print(f"Gemini: {comparison['gemini']['entity_count']} entities, {comparison['gemini']['relationship_count']} relationships, {comparison['gemini']['keyword_count']} keywords")
            
            print("\n--- Entity Overlap ---")
            print(f"Common entities: {len(common_entities)}")
            print(f"SpaCy only: {len(spacy_only)}")
            print(f"Gemini only: {len(gemini_only)}")
            
            print("\n--- SpaCy Entities ---")
            for entity in spacy_results['entities']:
                print(f"  - {entity['text']} ({entity['entity_type']}) [confidence: {entity.get('confidence', 'N/A'):.2f}]")
            
            print("\n--- Gemini Entities ---")
            for entity in gemini_results['entities']:
                print(f"  - {entity['text']} ({entity['entity_type']}) [confidence: {entity.get('confidence', 'N/A'):.2f}]")
            
            print("\n--- Keywords Comparison ---")
            print("SpaCy Keywords:")
            for kw in spacy_results['keywords'][:10]:  # Show top 10
                print(f"  - {kw['text']} (relevance: {kw.get('relevance', 'N/A'):.2f})")
                
            print("\nGemini Keywords:")
            for kw in gemini_results['keywords'][:10]:  # Show top 10
                print(f"  - {kw['text']} (relevance: {kw.get('relevance', 'N/A'):.2f})")
        
        return comparison
    
    except Exception as e:
        logger.error(f"Error comparing entity extraction: {e}")
        return {
            "error": str(e),
            "spacy": {
                "entity_count": len(spacy_results['entities']),
                "relationship_count": len(spacy_results['relationships']),
                "keyword_count": len(spacy_results['keywords'])
            }
        }

def main():
    """Run comparison with CLI arguments."""
    parser = argparse.ArgumentParser(description='Compare spaCy and Gemini entity extraction')
    parser.add_argument('--input', '-i', help='Input text file to process (if not provided, uses sample text)')
    parser.add_argument('--format', '-f', choices=['text', 'json'], default='text', help='Output format')
    args = parser.parse_args()
    
    sample_text = """
    **Microsoft Azure** is a cloud computing platform created by Microsoft. It was launched in February 2010.
    John Smith, the CEO of Contoso, announced a partnership with Microsoft on January 15, 2023 in New York.
    The agreement will focus on developing new AI services for healthcare providers.
    
    The project will utilize Azure's machine learning capabilities to improve diagnostic accuracy.
    Dr. Emily Chen, a leading researcher in medical AI, will lead the technical implementation.
    
    Contoso plans to invest $50 million in this initiative over the next three years.
    """
    
    if args.input:
        try:
            with open(args.input, 'r') as f:
                text = f.read()
        except Exception as e:
            logger.error(f"Error reading input file: {e}")
            text = sample_text
    else:
        text = sample_text
    
    extract_and_compare(text, args.format)

if __name__ == "__main__":
    main() 