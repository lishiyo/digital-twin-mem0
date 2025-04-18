# Graphiti Entity and Relationship Filtering

This document outlines the filtering rules and criteria used for entities and relationships in the Graphiti knowledge graph.

## Gemini-Based Entity Extraction and Filtering

The system has been upgraded to use Google's Gemini API for entity extraction, which offers improved accuracy and capabilities over the previous spaCy-based approach.

### Gemini Entity Extraction Approach

Entity extraction with Gemini uses a prompt-based approach where we:

1. Request entities with specific attributes (text, label, position, confidence, context)
2. Set a low temperature (0.1) to get consistent, factual responses
3. Extract entities from structured JSON responses
4. Apply post-processing to standardize and filter entities

Key configuration constants:
```python
# Default Gemini model
DEFAULT_MODEL = "gemini-2.0-flash"

# Minimum confidence threshold for entity filtering
MIN_CONFIDENCE = 0.6

# Important entity types that we want to prioritize
IMPORTANT_ENTITY_TYPES = ["Person", "Organization", "Location", "Product", "Event", "Date", "Time"]

# Blacklist of items that should not be treated as entities
ENTITY_BLACKLIST = [
    "#", "##", "###", "####", "#####", "######",  # Markdown headers
    "*", "**", "_", "__", "~", "~~",              # Markdown formatting
    "-", "+", ">", ">>",                          # Markdown list/quote markers
    ".", ",", ":", ";", "!", "?",                 # Common punctuation
    "`", "```",                                   # Code blocks
]
```

### Gemini Entity Filtering Process

The filtering process with Gemini consists of several layers:

1. **In-Prompt Filtering**: The prompt explicitly instructs Gemini to:
   - Only include high-quality entities
   - Ignore common words and formatting markers
   - Consider bold text (surrounded by `**`) as potential entities

2. **Post-Processing Filtering**:
   - Entities with confidence scores below the minimum threshold (0.6) are removed
   - Entities without required attributes have default values applied
   - Entity types are mapped to our standard set using the `ENTITY_TYPE_MAPPING` dictionary

3. **Fallback Mechanism**:
   If the initial extraction fails, a more structured prompt is used with explicit format requirements to ensure proper JSON extraction.

### Relationship Extraction with Gemini

Relationship extraction uses entities as input and has several filtering considerations:

1. **Minimum Entity Requirement**: At least two entities must be present for relationship extraction
2. **Entity-Based Prompt**: Only extracted entities are considered for relationships
3. **Context Verification**: The prompt specifically asks for relationships "clearly supported by the text"
4. **Structured Output**: Relationships must include source, target, relationship type, and supporting context
5. **Relationship Type Mapping**: A comprehensive mapping system determines appropriate relationship types based on entity pairs:
   ```python
   relationship_map = {
       ("Person", "Organization"): "ASSOCIATED_WITH",
       ("Organization", "Person"): "HAS_MEMBER",
       ("Person", "Person"): "RELATED_TO",
       ("Person", "Location"): "LOCATED_IN",
       # Many more mappings...
   }
   ```

### Keyword Extraction

In addition to entities and relationships, Gemini extracts keywords with these filtering criteria:

1. **Relevance Scoring**: Each keyword has a relevance score between 0 and 1
2. **Limited Results**: Only the top N (default 10) keywords are retained
3. **Conceptual Focus**: The prompt specifically asks for "genuinely important keywords that represent key concepts"
4. **Usage Counting**: Each keyword includes an estimated count of appearances in the text

### Document Processing Workflow

The complete document processing workflow with Gemini includes:

1. Extract keywords from the entire document for overall context
2. Process entities by document chunk to maintain locality
3. Adjust entity positions to reference the original document
4. Extract relationships using the full set of entities
5. Return a structured result with entities, relationships, and keywords

### JSON Extraction and Error Handling

The system includes robust error handling for JSON extraction from Gemini responses:

1. **Pattern Matching**: Uses regex to identify JSON blocks in responses
2. **Multiple Formats**: Handles both list and dictionary-based response formats
3. **Fallback Methods**: If extraction fails, a more structured prompt is used
4. **Default Values**: Missing fields in entity responses are populated with defaults
5. **Error Logging**: Comprehensive logging of extraction failures


--------


## Entity Extraction and Filtering (Prior SpaCy Approach)

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