"""Entity extraction utilities using spaCy."""

import logging
import os
from typing import Dict, List, Optional, Set, Tuple, Any
from collections import defaultdict
import re
import json

import spacy
from spacy.tokens import Doc
from spacy.language import Language
from spacy.matcher import PhraseMatcher
from spacy.util import filter_spans

from app.services.ingestion.entity_extraction_gemini import RELATIONSHIP_TYPES

logger = logging.getLogger(__name__)

# Default spaCy model
DEFAULT_MODEL = "en_core_web_sm"

# Minimum confidence threshold for entity filtering
MIN_ENTITY_CONFIDENCE = 0.6

# Entity types we're interested in - mapped to our system entity types
ENTITY_TYPE_MAPPING = {
    "PERSON": "Person",
    "ORG": "Organization",
    "GPE": "Location",
    "LOC": "Location",
    "PRODUCT": "Product",
    "WORK_OF_ART": "Document",
    "EVENT": "Event",
    "DATE": "Date",
    "TIME": "Time",
    "MONEY": "Money",
    "PERCENT": "Percent",
    "NORP": "Group",  # Nationalities, religious or political groups
    "FAC": "Facility",  # Buildings, airports, highways, bridges, etc.
    "LAW": "Legal",  # Named documents made into laws
    "LANGUAGE": "Language",
    "ORDINAL": "Ordinal",
    "CARDINAL": "Cardinal",
    "QUANTITY": "Quantity"
}

# Blacklist of items that should not be treated as entities
ENTITY_BLACKLIST = [
    "#", "##", "###", "####", "#####", "######",  # Markdown headers
    "*", "**", "_", "__", "~", "~~",              # Markdown formatting
    "-", "+", ">", ">>",                          # Markdown list/quote markers
    ".", ",", ":", ";", "!", "?",                 # Common punctuation
    "`", "```",                                   # Code blocks
]

# Common Markdown patterns to check against
MARKDOWN_PATTERNS = [
    "#", "##", "###", "####", "#####", "######",  # Headers
    "*", "**", "_", "__", "-", "+", ">",          # Formatting and lists
    "```", "`",                                   # Code blocks
    "![", "[", "](", ")",                         # Links and images
]

# Important entity types that we want to prioritize and preserve
IMPORTANT_ENTITY_TYPES = ["Person", "Organization", "Location", "Product", "Event", "Date", "Time"]

# Name patterns for detecting person names in text
NAME_PATTERNS = [
    r'with\s+([A-Z][a-z]+)[\s,]',
    r'and\s+([A-Z][a-z]+)[\s,]',
    r'by\s+([A-Z][a-z]+)[\s,]',
    r'from\s+([A-Z][a-z]+)[\s,]',
    r'for\s+([A-Z][a-z]+)[\s,]',
    r'to\s+([A-Z][a-z]+)[\s,]',
    r'of\s+([A-Z][a-z]+)[\s,]',
    r',\s+([A-Z][a-z]+),',  # Names in lists like "Alice, Bob, Charlie"
    r',\s+([A-Z][a-z]+)\s+and',  # "Alice, Bob and Charlie"
    r'(^|[\s,])([A-Z][a-z]+)(\s+and\s|\s+,\s)',  # Name at beginning or after spaces/commas
    r'([A-Z][a-z]+)\'s\s',  # Possessive names, e.g., "John's book"
    r'\s([A-Z][a-z]+),'     # Names followed by commas
]

class EntityExtractor:
    """Class for extracting entities from text using spaCy."""
    
    _loaded_models: Dict[str, Language] = {}
    
    def __init__(self, model_name: str = DEFAULT_MODEL, min_confidence: float = MIN_ENTITY_CONFIDENCE):
        """Initialize the entity extractor.
        
        Args:
            model_name: Name of the spaCy model to use
            min_confidence: Minimum confidence threshold for entity filtering
        """
        self.model_name = model_name
        self.min_confidence = min_confidence
        self._ensure_model_loaded()
    
    def _ensure_model_loaded(self) -> Language:
        """Ensure the spaCy model is loaded.
        
        Returns:
            Loaded spaCy model
        """
        if self.model_name not in self._loaded_models:
            try:
                # Try to load the model
                logger.info(f"Loading spaCy model: {self.model_name}")
                self._loaded_models[self.model_name] = spacy.load(self.model_name)
            except OSError:
                # If model isn't downloaded, try to download it
                logger.warning(f"SpaCy model {self.model_name} not found. Attempting to download...")
                try:
                    os.system(f"python -m spacy download {self.model_name}")
                    self._loaded_models[self.model_name] = spacy.load(self.model_name)
                except Exception as e:
                    logger.error(f"Failed to download spaCy model: {e}")
                    # Fallback to en_core_web_sm if it's not what we tried initially
                    if self.model_name != "en_core_web_sm":
                        logger.warning("Falling back to en_core_web_sm")
                        self.model_name = "en_core_web_sm"
                        return self._ensure_model_loaded()
                    else:
                        raise
        
        return self._loaded_models[self.model_name]
    
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
        
        # Get the model
        nlp = self._ensure_model_loaded()
        
        # First extract entities from bold text directly - this ensures we don't miss important multi-word terms
        entities = []
        
        # Instead, look for general name patterns in the text
        for pattern in NAME_PATTERNS:
            for match in re.finditer(pattern, text):
                # Extract the name from the match
                name = None
                if isinstance(match.groups()[0], tuple):
                    # Multiple capture groups - find the one that looks like a name
                    for group in match.groups():
                        if group and isinstance(group, str) and len(group) > 1 and group[0].isupper():
                            name = group
                            break
                else:
                    # Single capture group
                    group = match.group(1) if len(match.groups()) > 0 else match.group(0)
                    if group and len(group) > 1 and group[0].isupper():
                        name = group
                
                if name and len(name) >= 3:  # Ensure name is reasonable length
                    logger.debug(f"Found name pattern: {name}")
                    entity = {
                        "text": name,
                        "label": "PERSON",
                        "entity_type": "Person",
                        "start": match.start(),
                        "end": match.start() + len(name),
                        "sentence_id": 0,  # Will calculate later if needed
                        "context": text[max(0, match.start()-30):min(len(text), match.start() + len(name) + 30)],
                        "chunk_index": chunk_index,
                        "confidence": 0.85  # High confidence for pattern-matched names
                    }
                    entities.append(entity)
        
        # Extract bold text directly (before running spaCy)
        bold_pattern = r'\*\*(.*?)\*\*'  # **text**
        for match in re.finditer(bold_pattern, text):
            formatted_text = match.group(1).strip()
            
            # Basic filtering
            if len(formatted_text) <= 2 or formatted_text.startswith(("http://", "https://", "www.")):
                continue
                
            # Add multi-word bold text as entities directly
            if " " in formatted_text and formatted_text[0].isupper():
                entity_type = "Custom"
                # Try to determine entity type based on patterns
                if any(term in formatted_text for term in ["Inc", "Corp", "Ltd", "LLC", "Company", "Technologies", "Cloud"]):
                    entity_type = "Organization"
                elif "Hub" in formatted_text or "Service" in formatted_text or "Platform" in formatted_text:
                    entity_type = "Product"
                    
                entity = {
                    "text": formatted_text,
                    "label": "BOLD_TEXT",
                    "entity_type": entity_type,
                    "start": match.start(),
                    "end": match.end(),
                    "sentence_id": 0,  # Will calculate later if needed
                    "context": text[max(0, match.start()-30):min(len(text), match.end()+30)],
                    "chunk_index": chunk_index,
                    "confidence": 0.9  # We assign high confidence to bold text entities
                }
                entities.append(entity)
        
        # Process the text with spaCy
        doc = nlp(text)
        
        # Create a more focused blacklist
        MINIMAL_BLACKLIST = [
            "this", "that", "these", "those", "here", "there", 
            "when", "why", "how", "what", "which",
            "yes", "no", "not", "any", "some", "many", "few", "most"
        ] + ENTITY_BLACKLIST

        # Add debugging for transparency
        filtered_count = 0
        
        # Extract entities from spaCy
        for ent in doc.ents:
            entity_text = ent.text.strip()
            
            # Check if this is a capitalized acronym or abbreviation (2-3 letters, all caps)
            is_acronym = len(entity_text) <= 3 and entity_text.isupper()
            
            # Check if this is a date entity
            is_date = ent.label_ in ["DATE", "TIME"]
            
            # Check if this is an important entity type (we want to preserve these)
            is_important_entity = ENTITY_TYPE_MAPPING.get(ent.label_, "Unknown") in IMPORTANT_ENTITY_TYPES
            
            # Skip entities in the minimal blacklist (unless it's an acronym or important entity)
            if entity_text.lower() in MINIMAL_BLACKLIST and not (is_acronym or is_important_entity):
                filtered_count += 1
                logger.debug(f"Filtered entity (blacklist): {entity_text}")
                continue
                
            # Skip entities that are just one character (even acronyms need at least 2 chars)
            if len(entity_text) <= 1:
                filtered_count += 1
                logger.debug(f"Filtered entity (too short): {entity_text}")
                continue
                
            # Skip entities that are just numbers (unless they're dates/times)
            if (not is_date and entity_text.isdigit()):
                logger.debug(f"Skipping numeric non-Date entity: {entity_text}")
                filtered_count += 1
                continue
                
            # Skip entities that look like Markdown formatting
            if any(entity_text.startswith(pattern) for pattern in MARKDOWN_PATTERNS):
                continue
                
            # Skip entities that are entirely markdown symbols
            if all(char in "#*_-+>[]()!`" for char in entity_text):
                continue
                
            # Skip emojis and emoticons
            if entity_text in [':)', ':(', ':P', ':D', ':p', ';)', ':/'] or (len(entity_text) <= 3 and ':' in entity_text):
                continue
                
            # Skip URLs
            if entity_text.startswith(("http://", "https://", "www.")):
                continue
                
            # Skip email addresses
            if "@" in entity_text and "." in entity_text:
                filtered_count += 1
                logger.debug(f"Filtered entity (email): {entity_text}")
                continue
            
            # Calculate entity confidence
            confidence = self._get_entity_confidence(ent)
            
            # Skip low confidence entities unless they meet certain criteria
            if confidence < self.min_confidence:
                # Keep anyway if it's a proper noun with good context
                if (ent.label_ in ["PERSON", "ORG", "GPE", "PRODUCT", "WORK_OF_ART"] and 
                    entity_text[0].isupper()):
                    # Let these through, but with a note
                    logger.debug(f"Keeping low confidence entity due to context: {entity_text} ({ent.label_})")
                # Else skip
                else:
                    logger.debug(f"Skipping low confidence entity: {entity_text} ({ent.label_}, conf={confidence:.2f})")
                    continue
                
            # Map the spaCy entity type to our system type
            entity_type = ENTITY_TYPE_MAPPING.get(ent.label_, "Unknown")
            
            # Create entity object
            entity = {
                "text": ent.text,
                "label": ent.label_,
                "entity_type": entity_type,
                "start": ent.start_char,
                "end": ent.end_char,
                "sentence_id": self._get_sentence_id(doc, ent),
                "context": self._get_entity_context(doc, ent),
                "chunk_index": chunk_index,
                "confidence": confidence
            }
            
            entities.append(entity)
        
        logger.debug(f"Filtered {filtered_count} entities during extraction")
        
        # Add additional entities from formatted text (bold, italic, etc.)
        self._add_formatted_entities(text, entities, nlp, chunk_index, MINIMAL_BLACKLIST)
        
        return entities
    
    def _get_entity_confidence(self, ent) -> float:
        """Get the confidence score for an entity.
        
        Args:
            ent: spaCy entity
            
        Returns:
            Confidence score between 0 and 1
        """
        # Some newer models provide confidence scores directly
        if hasattr(ent, "_.") and hasattr(ent._, "confidence"):
            return ent._.confidence
            
        # If confidence isn't available, use heuristics to estimate it
        confidence = 0.7  # Baseline confidence
        
        # Check if this is an important entity type
        entity_type = ENTITY_TYPE_MAPPING.get(ent.label_, "Unknown")
        if entity_type in IMPORTANT_ENTITY_TYPES:
            confidence += 0.15  # Significant boost for important entities
        else:
            # Adjust based on entity type (if not already boosted as important)
            if ent.label_ in ["PERSON", "ORG", "GPE"]:
                confidence += 0.1  # These tend to be more reliable
        
        # Adjust based on entity length (longer entities tend to be more accurate)
        if len(ent.text) > 5:
            confidence += 0.05
            
        # Adjust based on capitalization (proper nouns are more likely to be entities)
        if ent.text[0].isupper():
            confidence += 0.1
            
        # Clamp to valid range
        return min(max(confidence, 0.0), 1.0)
    
    def _add_formatted_entities(self, text: str, entities: List[Dict[str, Any]], nlp: Language, 
                               chunk_index: int = 0, blacklist: List[str] = None) -> None:
        """Extract entities from formatted text.
        
        Args:
            text: Original text
            entities: List of entities to append to
            nlp: spaCy language model
            chunk_index: Index of the chunk this text belongs to
            blacklist: Optional blacklist of terms to skip
        """
        # Use the provided blacklist or fall back to the global one
        if blacklist is None:
            blacklist = ENTITY_BLACKLIST
            
        # Look for bold text patterns (**text**)
        # Future patterns can be added:
        # italic_pattern = r'\*(.*?)\*'  # *text*
        # underline_pattern = r'__(.*?)__'  # __text__
        
        # Find text between markdown formatting markers
        bold_pattern = r'\*\*(.*?)\*\*'  # **text**
        
        # Process bold text
        for match in re.finditer(bold_pattern, text):
            formatted_text = match.group(1).strip()
            
            # Apply same filtering as main entity extraction
            if (len(formatted_text) <= 2 or 
                formatted_text.lower() in blacklist or
                formatted_text.startswith(("http://", "https://", "www."))):
                continue
            
            # Process this text specifically
            formatted_doc = nlp(formatted_text)
            
            # If spaCy detected entities, add them
            if formatted_doc.ents:
                for ent in formatted_doc.ents:
                    confidence = self._get_entity_confidence(ent)
                    
                    # Skip low confidence entities
                    if confidence < self.min_confidence:
                        continue
                        
                    entity = {
                        "text": ent.text,
                        "label": ent.label_,
                        "entity_type": ENTITY_TYPE_MAPPING.get(ent.label_, "Unknown"),
                        "start": match.start() + ent.start_char,
                        "end": match.start() + ent.end_char,
                        "sentence_id": 0,  # Will need to calculate actual sentence ID
                        "context": formatted_text,
                        "chunk_index": chunk_index,
                        "confidence": confidence
                    }
                    entities.append(entity)
            else:
                # If no entities detected but the text is formatted in bold, 
                # treat the whole bold text as a custom entity
                # This change ensures multi-word entities like "Microsoft Azure" are captured
                if formatted_text[0].isupper():  # Capitalize first letter
                    entity_type = "Custom"
                    
                    # Try to determine a better entity type for common patterns
                    if any(term in formatted_text for term in ["Inc", "Corp", "Ltd", "LLC", "Company", "Technologies"]):
                        entity_type = "Organization"
                    elif "University" in formatted_text or "College" in formatted_text:
                        entity_type = "Organization"
                    elif any(word in formatted_text for word in ["API", "Service", "Platform", "Cloud", "Framework"]):
                        entity_type = "Product"
                    
                    entity = {
                        "text": formatted_text,
                        "label": "CUSTOM",
                        "entity_type": entity_type,
                        "start": match.start(),
                        "end": match.end(),
                        "sentence_id": 0,  # Will need to calculate actual sentence ID
                        "context": text[max(0, match.start()-30):min(len(text), match.end()+30)],
                        "chunk_index": chunk_index,
                        "confidence": 0.85  # Higher confidence for bold text
                    }
                    entities.append(entity)
    
    def extract_relationships(self, text: str) -> List[Dict[str, Any]]:
        """Extract potential relationships between entities.
        
        This uses a simple heuristic approach - entities appearing in the same sentence
        might be related.
        
        Args:
            text: Text to extract relationships from
            
        Returns:
            List of potential relationships
        """
        if not text.strip():
            return []
        
        # Get the model
        nlp = self._ensure_model_loaded()
        
        # Process the text
        doc = nlp(text)
        
        # Group entities by sentence
        entities_by_sentence = defaultdict(list)
        
        for ent in doc.ents:
            sentence_id = self._get_sentence_id(doc, ent)
            entity_type = ENTITY_TYPE_MAPPING.get(ent.label_, "Unknown")
            
            entities_by_sentence[sentence_id].append({
                "text": ent.text,
                "label": ent.label_,
                "entity_type": entity_type,
                "start": ent.start_char,
                "end": ent.end_char,
            })
        
        # Find relationships within sentences (co-occurrence)
        relationships = []
        
        for sentence_id, entities in entities_by_sentence.items():
            # If there's only one entity in the sentence, no relationships
            if len(entities) < 2:
                continue
            
            # Get the sentence for context
            sentence_text = ""
            for sent in doc.sents:
                if sent.start == sentence_id:
                    sentence_text = sent.text
                    break
            
            # Create relationships between all entities in the sentence
            for i, source in enumerate(entities):
                for target in entities[i+1:]:
                    # Skip self-relationships
                    if source["text"] == target["text"]:
                        continue
                    
                    # Determine relationship type based on entity types
                    rel_type = self._determine_relationship_type(source["entity_type"], target["entity_type"])
                    
                    relationships.append({
                        "source": source["text"],
                        "source_type": source["entity_type"],
                        "target": target["text"],
                        "target_type": target["entity_type"],
                        "relationship": rel_type,
                        "context": sentence_text,
                        "sentence_id": sentence_id
                    })
        
        # Ensure all relationships use valid relationship types from our centralized list
        for rel in relationships:
            if rel["relationship"] not in RELATIONSHIP_TYPES:
                rel["relationship"] = "MENTIONED_WITH"
    
        return relationships
    
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
        
        # Get the model
        nlp = self._ensure_model_loaded()
        
        # Process the text
        doc = nlp(text)
        
        # Count token frequencies (excluding stopwords and punctuation)
        token_freq = defaultdict(int)
        for token in doc:
            if not token.is_stop and not token.is_punct and not token.is_space:
                # Lemmatize the token to count variations together
                lemma = token.lemma_.lower()
                if len(lemma) > 1:  # Skip single characters
                    token_freq[lemma] += 1
        
        # Sort by frequency and take top N
        top_keywords = sorted(token_freq.items(), key=lambda x: x[1], reverse=True)[:top_n]
        
        # Format results
        keywords = []
        for keyword, count in top_keywords:
            keywords.append({
                "text": keyword,
                "count": count,
                "relevance": count / len(doc)  # Simple relevance score
            })
        
        return keywords
    
    def process_document(self, content: str, chunk_boundaries: List[Tuple[int, int]] = None) -> Dict[str, Any]:
        """Process a document and extract entities and relationships.
        
        Args:
            content: Document content
            chunk_boundaries: Optional list of chunk boundaries as (start, end) tuples
            
        Returns:
            Dictionary with extracted entities and relationships
        """
        if not content:
            return {"entities": [], "relationships": [], "keywords": []}
            
        # Extract keywords
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
            all_relationships = self.extract_relationships(content)
            
            return {
                "entities": all_entities,
                "relationships": all_relationships,
                "keywords": keywords
            }
        else:
            # Process the whole document as a single chunk
            entities = self.extract_entities(content)
            
            relationships = self.extract_relationships(content)
            
            return {
                "entities": entities,
                "relationships": relationships,
                "keywords": keywords
            }
    
    def _get_sentence_id(self, doc: Doc, entity) -> int:
        """Get the sentence ID (start token index) for an entity.
        
        Args:
            doc: spaCy Doc object
            entity: spaCy entity span
            
        Returns:
            Sentence start token index
        """
        for sent in doc.sents:
            if entity.start >= sent.start and entity.start < sent.end:
                return sent.start
        return 0
    
    def _get_entity_context(self, doc: Doc, entity, window: int = 10) -> str:
        """Get surrounding context for an entity.
        
        Args:
            doc: spaCy Doc object
            entity: spaCy entity span
            window: Number of tokens to include before and after
            
        Returns:
            Context string
        """
        start = max(0, entity.start - window)
        end = min(len(doc), entity.end + window)
        
        return doc[start:end].text
    
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
        }
        
        # Get relationship type from map, or use default
        return relationship_map.get((source_type, target_type), "MENTIONED_WITH") 