# Trait Extraction Agent Design

## 1. Overview

The Trait Extraction Agent is responsible for extracting user traits from multiple data sources and updating the UserProfile. This document outlines the design of a unified trait extraction system that works across different content sources (chat, documents, and future sources like calendar and social media).

## 2. Current State Analysis

### 2.1. Current Trait Extraction

Currently, trait extraction is implemented in two separate places:

1. **Chat Messages**: 
   - `ChatGraphitiIngestion` handles extraction from chat messages.
   - Extracted traits are added to Graphiti and UserProfile.
   - Uses the `EntityExtractor.extract_traits()` method (via `EntityExtractor.process_document()`).
   - Has confidence thresholds and conflict resolution for UserProfile updates.

2. **Documents**:
   - `IngestionService.process_file()` handles entity extraction from documents.
   - Extracts entities and relationships to graphiti, but doesn't update UserProfile with traits.
   - The `EntityExtractor.process_document()` method that it calls does actually extract traits, but they aren't used.

### 2.2. Limitations of Current Approach

1. **Lack of Unified Interface**: Different data sources have different extraction pipelines.
2. **Tight Coupling**: Trait extraction is coupled with Graphiti operations.
3. **Inconsistent User Profile Updates**: Only chat-based traits are stored in UserProfile.
4. **Redundant Logic**: Similar extraction logic is duplicated in different places.
5. **No Confidence-Based Merging**: No universal approach to handle contradictions between sources.

## 3. Design Goals

1. **Source Independence**: Extract traits from any source with a consistent interface.
2. **Decoupled Services**: Separate trait extraction from other operations (Graphiti, Mem0).
3. **Consistent UserProfile Updates**: Apply the same update policies across all sources.
4. **Confidence-Based Merging**: Prioritize traits based on confidence and source reliability.
5. **Extensibility**: Easy addition of new sources without modifying existing code.

## 4. Architecture

### 4.1. Component Overview

```
┌───────────────────┐     ┌────────────────────┐      ┌──────────────────┐
│                   │     │                    │      │                  │
│   Data Sources    │────▶│ Trait Extractors   │─────▶│ Trait Processor  │
│                   │     │                    │      │                  │
└───────────────────┘     └────────────────────┘      └────────┬─────────┘
    Chat                   Source-specific                     │
    Documents              extractors with                     │
    Calendar               standard output                     │
    Social Media           format                              ▼
    ...                                                ┌──────────────────┐
                                                      │                  │
                                                      │  UserProfile     │
                                                      │  Updater         │
                                                      │                  │
                                                      └────────┬─────────┘
                                                               │
                                                               ▼
                                                      ┌──────────────────┐
                                                      │                  │
                                                      │  Graph Service   │
                                                      │  (Optional)      │
                                                      │                  │
                                                      └──────────────────┘
```

### 4.2. Key Components

#### 4.2.1. Trait Extraction Interface

A common interface for all trait extractors:

```python
class TraitExtractor(ABC):
    @abstractmethod
    async def extract_traits(self, content: Any, metadata: Dict[str, Any]) -> List[Trait]:
        """Extract traits from content with associated metadata."""
        pass
```

#### 4.2.2. Source-Specific Extractors

Specialized extractors for different data sources, these can be in one file `app/services/traits/extractors.py`:

1. **ChatTraitExtractor**: Extracts traits from chat messages
2. **DocumentTraitExtractor**: Extracts traits from documents
3. **CalendarTraitExtractor**: (Future) Extracts traits from calendar events
4. **SocialMediaTraitExtractor**: (Future) Extracts traits from social media posts

#### 4.2.3. Trait Processor

Processes extracted traits before updating the UserProfile:

- Applies source-specific confidence adjustments
- Validates trait format and content
- Filters out low-confidence traits
- Resolves conflicts between similar traits
- Adds source attribution

#### 4.2.4. UserProfile Updater

Updates the UserProfile with processed traits:

- Maps traits to appropriate UserProfile fields
- Handles conflicts with existing traits
- Applies confidence-based merging
- Maintains update history

#### 4.2.5. Trait Extraction Service

Orchestrates the entire process:

- Selects appropriate extractor based on source
- Invokes extraction, processing, and profile update
- Handles error conditions and retry logic
- Provides monitoring and metrics
- Optionally updates Graphiti (decoupled from core functionality)

## 5. Data Model

### 5.1. Trait Object

```python
class Trait(BaseModel):
    trait_type: Literal["skill", "interest", "preference", "dislike", "attribute"]
    name: str
    confidence: float
    evidence: str
    source: str  # What type of source: "chat", "document", "calendar", etc.
    source_id: Optional[str]  # Specific ID of the source (message_id, document_path, etc.)
    context: Optional[str]  # Additional context (e.g., conversation title)
    strength: Optional[float]  # How strongly this trait is expressed (0.0-1.0)
    extracted_at: datetime
    metadata: Dict[str, Any] = {}  # Additional source-specific metadata
```

### 5.2. Extraction Request

```python
class TraitExtractionRequest(BaseModel):
    content: Any  # Source-specific content (text, structured data, etc.)
    source_type: str  # "chat", "document", "calendar", "social_media"
    user_id: str
    metadata: Dict[str, Any] = {}  # Source-specific metadata
    options: Dict[str, Any] = {}  # Extraction options
```

### 5.3. Extraction Result

```python
class TraitExtractionResult(BaseModel):
    traits: List[Trait]
    status: str
    user_id: str
    source_type: str
    profile_updates: Dict[str, Any]  # What was updated in the profile
    errors: List[str] = []
    warnings: List[str] = []
```

## 6. Implementation Strategy

### 6.1. Phase 1: Core Service and Document Integration

- [x] Create the `TraitExtractor` interface and base classes
- [x] Implement the `TraitExtractionService` with core logic
- [x] Refactor existing chat trait extraction into `ChatTraitExtractor`
- [x] Implement `DocumentTraitExtractor` for documents
- [x] Modify `IngestionService` to use the new Trait Extraction Service
- [x] Add UserProfile updates for document-extracted traits
- [x] Test with chat and document sources

### 6.2. Phase 2: Advanced Processing

- [ ] Implement advanced confidence scoring (see 7. Confidence & Merging Strategy below)
- [ ] Add cross-source trait validation
- [ ] Implement temporal weighting for trait confidence
- [ ] Add conflict resolution for contradictory traits
- [ ] Create trait evolution tracking for UserProfile, this means maintaining a history of how a user's traits change over time:
    - when a trait was first detected
    - how its confidence score has changed over time
    - What evidence supported it at different points
    - If it has been contradicted or reinforced by different sources
- [ ] Develop trait categorization for better organization, this means organizing traits into a more structured hierarchy rather than flat lists, for example:
    - Hierarchical skills: Instead of just "Python programming" and "JavaScript programming" as separate skills, they would be categorized as "Programming > Python" and "Programming > JavaScript"
    - Interest domains: Grouping interests into domains like "Technology", "Arts", "Sports", etc.
    - Related preferences: Connecting preferences that are related (e.g., "prefers dark mode" and "prefers low light conditions" might be related UI/environment preferences)
    - Trait relationships: Establishing semantic relationships between traits (e.g., "likes hiking" is related to "enjoys nature" and "values physical fitness")

### 6.3. Phase 3: Additional Sources

- [ ] Implement calendar integration and `CalendarTraitExtractor`
- [ ] Add social media support with `SocialMediaTraitExtractor`
- [ ] Create specialized extractors for other sources
- [ ] Implement source reliability weighting

## 7. Confidence & Merging Strategy

### 7.1. Source Reliability Weights

Different sources may have different reliability weights:

- User explicit statements (high): 0.9
- Chat messages (user): 0.8
- Documents (user-authored): 0.8
- Documents (third-party): 0.7
- Calendar entries: 0.75
- Social media: 0.6

### 7.2. Confidence Calculation

Final confidence is calculated as:

```
final_confidence = base_confidence * source_reliability * recency_factor
```

Where:
- `base_confidence` is the initial confidence from the extractor
- `source_reliability` is the weight for the source type
- `recency_factor` decays older traits (e.g., 1.0 for new, 0.9 for old)

### 7.3. Conflict Resolution

When conflicting traits are found:

- [x] If new trait has higher confidence, replace old one
- [x] If confidences are close (within 0.1), merge evidence and boost confidence
- [x] If old trait has significantly higher confidence, keep it
- [ ] For contradictory traits, maintain both but mark the relationship

## 8. Integration Points

### 8.1. IngestionService Changes

- [x] Modify `process_file()` to call the Trait Extraction Service, extracted traits should update UserProfile
- [x] Decouple entity and relationship extraction from UserProfile updates
- [ ] Make Graphiti operations optional

### 8.2. Conversation Pipeline Changes

- [x] Refactor `ChatGraphitiIngestion` to use the Trait Extraction Service
- [x] Keep existing functionality but delegate trait processing

### 8.3. Metrics and Feedback

- [ ] Add tracking for trait extraction accuracy
- [ ] Create feedback loop for incorrect traits
- [ ] Implement confidence adjustment based on user feedback

## 9. Testing Strategy

1. **Unit Tests**: Test each extractor and processor component
2. **Integration Tests**: Test the full extraction pipeline
3. **Conflict Resolution Tests**: Verify merging strategies work as expected
4. **Cross-Source Tests**: Ensure consistent behavior across sources
5. **Performance Tests**: Measure throughput and latency

## 10. Future Enhancements

1. **Active Learning**: Improve extraction based on user feedback
2. **Contextual Confidence**: Adjust confidence based on surrounding context
3. **Topic-Specific Extractors**: Specialized extractors for domains like tech, sports, cooking
4. **Relationship Extraction**: Extract not just traits but relationships between them
5. **Temporal Understanding**: Track how traits change over time
