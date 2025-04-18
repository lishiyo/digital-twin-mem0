"""Entity extraction utilities using spaCy."""

import logging
import os
from typing import Dict, List, Optional, Set, Tuple, Any
from collections import defaultdict
import re

import spacy
from spacy.tokens import Doc
from spacy.language import Language

logger = logging.getLogger(__name__)

# Default spaCy model
DEFAULT_MODEL = "en_core_web_sm"

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

class EntityExtractor:
    """Class for extracting entities from text using spaCy."""
    
    _loaded_models: Dict[str, Language] = {}
    
    def __init__(self, model_name: str = DEFAULT_MODEL):
        """Initialize the entity extractor.
        
        Args:
            model_name: Name of the spaCy model to use
        """
        self.model_name = model_name
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
    
    def extract_entities(self, text: str) -> List[Dict[str, Any]]:
        """Extract entities from text.
        
        Args:
            text: Text to extract entities from
            
        Returns:
            List of extracted entities with details
        """
        if not text.strip():
            return []
        
        # Get the model
        nlp = self._ensure_model_loaded()
        
        # Process the text
        doc = nlp(text)
        
        # Extract entities
        entities = []
        for ent in doc.ents:
            entity_text = ent.text.strip()
            
            # Skip entities in the blacklist
            if entity_text in ENTITY_BLACKLIST:
                continue
                
            # Skip entities that are just one character
            if len(entity_text) <= 1:
                continue
                
            # Skip entities that are just numbers (unless they're dates/times)
            if (ent.label_ not in ["DATE", "TIME"] and 
                entity_text.isdigit()):
                continue
                
            # Skip entities that look like Markdown formatting
            if any(entity_text.startswith(pattern) for pattern in MARKDOWN_PATTERNS):
                continue
                
            # Skip entities that are entirely markdown symbols
            if all(char in "#*_-+>[]()!`" for char in entity_text):
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
                "context": self._get_entity_context(doc, ent)
            }
            
            entities.append(entity)
        
        # Add additional entities from formatted text (bold, italic, etc.)
        self._add_formatted_entities(text, entities, nlp)
        
        return entities
    
    def _add_formatted_entities(self, text: str, entities: List[Dict[str, Any]], nlp: Language) -> None:
        """Extract entities from formatted text.
        
        Args:
            text: Original text
            entities: List of entities to append to
            nlp: spaCy language model
        """
        # Look for bold text patterns (**text**)
        # Future patterns can be added:
        # italic_pattern = r'\*(.*?)\*'  # *text*
        # underline_pattern = r'__(.*?)__'  # __text__
        
        # Find text between markdown formatting markers
        bold_pattern = r'\*\*(.*?)\*\*'  # **text**
        
        # Process bold text
        for match in re.finditer(bold_pattern, text):
            formatted_text = match.group(1).strip()
            if len(formatted_text) <= 1 or formatted_text in ENTITY_BLACKLIST:
                continue
            
            # Process this text specifically
            formatted_doc = nlp(formatted_text)
            
            # If spaCy detected entities, add them
            if formatted_doc.ents:
                for ent in formatted_doc.ents:
                    entity = {
                        "text": ent.text,
                        "label": ent.label_,
                        "entity_type": ENTITY_TYPE_MAPPING.get(ent.label_, "Unknown"),
                        "start": match.start() + ent.start_char,
                        "end": match.start() + ent.end_char,
                        "sentence_id": 0,  # Will need to calculate actual sentence ID
                        "context": formatted_text
                    }
                    entities.append(entity)
            else:
                # If no entities detected but the text looks like an entity
                # (e.g., proper noun), add it as a custom entity
                if formatted_text[0].isupper() and len(formatted_text.split()) <= 4:
                    entity = {
                        "text": formatted_text,
                        "label": "CUSTOM",
                        "entity_type": "Custom",
                        "start": match.start(),
                        "end": match.end(),
                        "sentence_id": 0,  # Will need to calculate actual sentence ID
                        "context": text[max(0, match.start()-30):min(len(text), match.end()+30)]
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
    
    def process_document(self, content: str) -> Dict[str, Any]:
        """Process a document to extract entities, relationships, and keywords.
        
        Args:
            content: Document content
            
        Returns:
            Dictionary with extracted information
        """
        # Extract entities, relationships, and keywords
        entities = self.extract_entities(content)
        relationships = self.extract_relationships(content)
        keywords = self.extract_keywords(content)
        
        # Deduplicate entities by text (case-insensitive)
        unique_entities = {}
        for entity in entities:
            entity_key = entity["text"].lower()
            if entity_key not in unique_entities:
                unique_entities[entity_key] = entity
            else:
                # If we see the entity again, increment a count for it
                if "count" in unique_entities[entity_key]:
                    unique_entities[entity_key]["count"] += 1
                else:
                    unique_entities[entity_key]["count"] = 2
        
        # Return all extracted information
        return {
            "entities": list(unique_entities.values()),
            "relationships": relationships,
            "keywords": keywords,
            "summary": {
                "entity_count": len(unique_entities),
                "relationship_count": len(relationships),
                "keyword_count": len(keywords)
            }
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