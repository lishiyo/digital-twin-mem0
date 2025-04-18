# Graphiti Entity and Relationship Filtering

This document outlines the filtering rules and criteria used for entities and relationships in the Graphiti knowledge graph.

## Entity Filtering

Entities extracted during document ingestion are filtered using the following criteria:

### Entity Extraction and Filtering (Centralized in EntityExtractor)

All entity filtering now happens in a single place - the `EntityExtractor` class in `entity_extraction.py`. This centralized approach provides consistency and avoids redundant filtering.

Key filtering constants:
```python
# Minimum confidence threshold for entity filtering
MIN_ENTITY_CONFIDENCE = 0.6

# Important entity types that we want to prioritize and preserve
IMPORTANT_ENTITY_TYPES = ["Person", "Organization", "Location", "Product", "Event", "Date", "Time"]

# A minimal blacklist for common terms
MINIMAL_BLACKLIST = [
    "this", "that", "these", "those", "here", "there", 
    "when", "why", "how", "what", "which",
    "yes", "no", "not", "any", "some", "many", "few", "most"
]
```

### Entity Filtering Logic

Entities are filtered out if they meet any of these criteria:
- Entity text is in the minimal blacklist (unless it's an acronym or important entity type)
- Entity is just one character long
- Entity is just a number (unless it's a date/time entity)
- Entity looks like Markdown formatting
- Entity is entirely made of markdown symbols
- Entity is an emoji or emoticon
- Entity is a URL
- Entity is an email address
- Entity has low confidence score (below MIN_ENTITY_CONFIDENCE)

### Special Handling for Important Entities

The system gives special treatment to certain entity types:

1. **Important Entity Types** - Entities of types in the `IMPORTANT_ENTITY_TYPES` list receive:
   - Guaranteed preservation during filtering
   - A confidence boost of 0.15 to their baseline score

2. **Acronyms** - Entities that are 2-3 letters and all uppercase:
   - Bypass common filtering rules (exemption from blacklist)
   - Preserves important technical terms like "AI", "ML", etc.

3. **Date and Time Entities** - Entities with label "DATE" or "TIME":
   - Skip numeric filtering (allowing dates like "2023")
   - Higher preservation priority

### Confidence Scoring System

The confidence scoring mechanism has been enhanced to better reflect entity reliability:

```python
def _get_entity_confidence(self, ent) -> float:
    # Baseline confidence
    confidence = 0.7
    
    # Check if this is an important entity type
    entity_type = ENTITY_TYPE_MAPPING.get(ent.label_, "Unknown")
    if entity_type in IMPORTANT_ENTITY_TYPES:
        confidence += 0.15  # Significant boost for important entities
    else:
        # Adjust based on entity type (if not already boosted as important)
        if ent.label_ in ["PERSON", "ORG", "GPE"]:
            confidence += 0.1  # These tend to be more reliable
    
    # Adjust based on entity length
    if len(ent.text) > 5:
        confidence += 0.05
        
    # Adjust based on capitalization
    if ent.text[0].isupper():
        confidence += 0.1
        
    # Clamp to valid range
    return min(max(confidence, 0.0), 1.0)
```

### Entity Prioritization

When processing entities for inclusion in the knowledge graph:

1. Entities are first **sorted by confidence score** (highest first), then by length (longest first) as a secondary criterion
2. This ensures that if we hit the maximum entity limit per chunk (currently 20), we keep the most reliable entities
3. The confidence-first approach guarantees that important, high-confidence entities are preserved even in dense documents

### Additional Entity Processing

For each document chunk, we:
- Extract entities using spaCy
- Extract bold text as entities (higher confidence)
- Apply the filtering logic described above
- Track and log filtered entities for transparency

### Person Name Extraction from Longer Texts

For long entity text blocks, we extract potential person names using regex patterns:

```python
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
```

These patterns look for capitalized words after prepositions or in list constructs that are likely to be person names.

## Relationship Filtering

Relationship filtering has been simplified with the centralization of entity filtering:

### Basic Relationship Filtering

- Relationships are only kept if both source and target entities exist in the filtered entity list
- For each file, a maximum of `MAX_RELATIONSHIPS_TOTAL` (currently 40) relationships are processed
- Duplicate relationships are skipped using a `processed_rels` set to track already processed relationships

The simplified relationship filtering logic:

```python
# Filter relationships to only include valid entities
valid_entity_texts = {entity["text"] for entity in filtered_entities}
filtered_relationships = []

for rel in extraction_results["relationships"]:
    source_text = rel["source"]
    target_text = rel["target"]
    
    # Standard check - both entities must be in the filtered list
    if source_text in valid_entity_texts and target_text in valid_entity_texts:
        filtered_relationships.append(rel)
    else:
        # Log detailed reason for filtering
        if source_text not in valid_entity_texts and target_text not in valid_entity_texts:
            filtered_reason = "both source and target entities missing from filtered list"
        elif source_text not in valid_entity_texts:
            filtered_reason = f"source entity '{source_text}' missing from filtered list"
        else:
            filtered_reason = f"target entity '{target_text}' missing from filtered list"
            
        logger.info(f"Filtered out invalid relationship: {rel} (Reason: {filtered_reason})")
```

## Entity Creation Logic

When creating entities in Graphiti:

1. We first check if the entity already exists in the graph using `find_entity`
2. If it exists, we use the existing entity ID
3. If not, we create a new entity with the specified properties, scope, and owner_id
4. Entity IDs are tracked in an `entity_id_map` for relationship creation
5. Scope and owner_id are added to all entities for proper access control

## Relationship Creation Logic

When creating relationships in Graphiti:

1. We check if a relationship already exists between the source and target entities with the same type and scope
2. If it exists, we skip creating a duplicate relationship
3. If not, we create a new relationship with specified properties including scope and owner_id

## Performance Considerations

- Entity filtering happens in a single place (EntityExtractor) for better maintainability
- Detailed logging helps track what entities are filtered and why
- Special handling for important entity types, acronyms, and dates improves extraction quality
- Entities extracted during named entity recognition receive confidence scores
- Relationships are only processed if both entities exist in the graph
- Both entity and relationship counts are capped to prevent overload from large documents

## Current Improvements

Recent improvements to the filtering logic:

1. **Centralized Filtering**: All filtering logic now resides in `entity_extraction.py` for better maintainability
2. **Enhanced Confidence Scoring**: Important entities receive higher confidence scores
3. **Special Handling for Acronyms and Dates**: Prevents filtering of important short entities
4. **Simplified Relationship Filtering**: No redundant filtering, clarity in relationship creation
5. **Improved Transparency**: Better logging of filtered entities and relationships
6. **Consistent Scope and Owner**: Added to all entities and relationships for proper access control
7. **Confidence-Based Prioritization**: Entities are now sorted by confidence score first, ensuring highest-quality entities are preserved when limits are reached

## Future Improvements

Potential improvements to the filtering logic:

1. Consider using a larger Spacy model for better entity recognition
2. Add domain-specific entity extraction rules
3. Implement more sophisticated filtering based on entity types
4. Fine-tune filtering parameters based on document types
5. Introduce similarity checks to avoid near-duplicate entities
6. Add adaptive confidence thresholds based on document type
7. Integrate machine learning for entity importance determination 