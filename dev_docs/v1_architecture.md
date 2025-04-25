# Digital Twin V1 Architecture

This document outlines the architecture, design patterns, and key components of our Digital Twin V1 system. It's intended to provide architectural guidance as we complete the remaining tasks in the v1 roadmap.

## System Overview

The Digital Twin V1 is a personal digital representation that models a user's preferences, skills, interests, and relationships based on multiple data sources. It can:

1. Answer questions by retrieving relevant information from memory and knowledge graph
2. Make personalized recommendations based on the user's profile and external context
3. Learn and adapt from continuous user interactions
4. Ingest and process data from multiple sources (documents, chat logs, calendar, social media, etc.)

## Core Components

### 1. Data Ingestion Layer

This layer handles the intake of various data sources and their transformation into standardized internal formats.

**Key Components:**
- **Document Ingestion Pipeline**: Processes uploaded files (already implemented)
- **Chat Ingestion Pipeline**: Processes conversation history (implemented)
- **Calendar Connector**: OAuth integration with Google Calendar (upcoming)
- **Social Media Connector**: Twitter/X data scraping and analysis (upcoming)
- **Ingestion Orchestrator**: Manages the ingestion workflow across sources

**Design Patterns:**
- **Adapter Pattern**: Each source has a dedicated adapter to transform source-specific data to our internal format
- **Pipeline Pattern**: Multi-stage processing with clear boundaries between stages
- **Factory Pattern**: Create appropriate transformers based on data source type

### 2. Storage Layer

Manages persistent storage of various data types across multiple backends.

**Key Components:**
- **PostgreSQL Database**: Relational storage for user data, conversations, and structured profiles
- **Mem0**: Vector database for semantic search and retrieval of text-based memories
- **Graphiti**: Knowledge graph for modeling relationships between entities, traits, and concepts

**Design Patterns:**
- **Repository Pattern**: Abstract data access with repositories for each model type
- **Unit of Work**: Manage transactions and ensure data consistency
- **Decorator Pattern**: Add features like caching or logging to repositories without modifying their core logic

### 3. Memory & Knowledge Management

Responsible for organizing, maintaining, and retrieving information.

**Key Components:**
- **Memory Service**: Interface to Mem0 for storing and retrieving memories
- **Graph Service**: Interface to Graphiti for managing knowledge graph operations
- **Extraction Pipeline**: Unified service (`app/services/extraction_pipeline.py`) coordinating entity, relationship, and trait extraction.
- **Entity Extraction**: LLM-based extraction of entities and relationships from raw text (via `ExtractionPipeline`).
- **Trait Extraction Service**: Dedicated service (`app/services/traits/service.py`) for extracting user traits (preferences, skills, interests) from various sources and updating UserProfile.
- **Profile Manager**: Maintain and update UserProfile with confidence scoring and conflict resolution (partially handled by `TraitExtractionService`).

**Design Patterns:**
- **Strategy Pattern**: Pluggable strategies for memory retrieval, entity/trait extraction (within `ExtractionPipeline`).
- **Observer Pattern**: Profile updates notify subscribers about changes
- **Command Pattern**: Encapsulate graph operations as commands with undo capability

### 4. Agent Layer

Implements the digital twin's core reasoning and decision-making capabilities.

**Key Components:**
- **LangGraph Agent**: Orchestrates the reasoning flow using a graph of specialized nodes
- **Context Synthesis**: Merges profile data with retrieved memories and graph facts
- **Recommendation Engine**: Generates personalized recommendations based on user profile and context
- **Feedback Processor**: Updates the user model based on explicit and implicit feedback

**Design Patterns:**
- **Chain of Responsibility**: Pass requests through a chain of processing nodes
- **Mediator Pattern**: Coordinate between different agent components
- **Template Method**: Define skeleton of agent operations with specific steps implemented by subclasses

### 5. API Layer

Exposes the digital twin's capabilities through standardized REST interfaces.

**Key Components:**
- **API Routers**: FastAPI routers for different functional areas (chat, profile, recommendations, etc.)
- **Request Validators**: Ensure incoming requests meet contract specifications
- **Response Formatters**: Standardize API responses
- **Authentication & Authorization**: Secure API access

**Design Patterns:**
- **Façade Pattern**: Simplify complex subsystem interactions with a unified interface
- **Dependency Injection**: Provide dependencies to API handlers
- **Rate Limiting**: Protect against abuse

### 6. Background Processing

Handles asynchronous tasks and scheduled operations.

**Key Components:**
- **Celery Workers**: Execute tasks asynchronously
- **Task Queue**: Store pending tasks (Redis)
- **Periodic Task Scheduler**: Trigger recurring operations (ingestion refreshes, etc.)
- **Status Tracking**: Monitor and report on background task status

**Design Patterns:**
- **Producer-Consumer**: Separate task creation from execution
- **Retry Pattern**: Handle temporary failures with exponential backoff
- **Circuit Breaker**: Prevent cascading failures in external service calls

## Key Architectural Patterns

### Event-Driven Architecture

For loose coupling between components, we use an event-driven approach for certain operations:

- **Event Publishers**: Components emit events when significant state changes occur
- **Event Subscribers**: Components that react to events from other parts of the system
- **Event Bus**: Central channel for publishing and subscribing to events

This allows for extensibility and separation of concerns, particularly for the trait extraction and profile update flows.

### Layered Architecture

The system follows a layered architecture with clear separation of concerns:

1. **Presentation Layer**: API endpoints and response formatting
2. **Application Layer**: Orchestration of use cases and business logic
3. **Domain Layer**: Core business entities and logic (User, UserProfile, etc.)
4. **Infrastructure Layer**: Technical capabilities (database, external services, etc.)

### Hexagonal Architecture (Ports and Adapters)

For external integrations, we follow a ports and adapters pattern:

- **Ports**: Abstract interfaces defining how the application interacts with external systems
- **Adapters**: Concrete implementations of ports for specific technologies or services

This pattern makes it easier to add new data sources or swap out existing ones without affecting core business logic.

## Data Flow

### Ingestion Flow

1. Data enters through source-specific adapters
2. Raw data is transformed into internal formats
3. **Extraction Pipeline** processes content:
    - Extracts entities and relationships (for Graphiti, if enabled)
    - Invokes **Trait Extraction Service**
4. **Trait Extraction Service** processes extracted traits and updates **UserProfile** (if enabled)
5. Extracted entities/relationships/traits are potentially stored in **Graphiti** (if enabled)
6. Memories are stored in **Mem0** with metadata (handled separately, e.g., by `ChatMem0Ingestion` or document ingestion)

### Query Flow

1. User query arrives through API
2. Context is built from:
   - UserProfile data
   - Relevant memories from Mem0
   - Relevant facts from Graphiti
3. LangGraph agent processes the query with context
4. Response is generated and returned
5. Interaction is logged and fed back into ingestion flow

### Recommendation Flow

1. External context is provided through API
2. UserProfile is retrieved
3. Relevant memories and graph facts are gathered
4. Recommendation engine generates personalized suggestions
5. Recommendations are returned with justifications
6. User feedback is collected and used to refine the model

## Interactions Between Components

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│     Sources     │     │      API        │     │     Agent       │
│  (Data Origins) │     │    (Routes)     │     │   (Reasoning)   │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│    Ingestion    │     │    Services     │     │Context Synthesis│
│   (Adapters)    │────▶│ (Orchestration) │◄────│ (Data Merging)  │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ExtractionPipeline│◄───┤Trait Extraction │     │ Recommendation  │
│(Entities/Rels)  │     │    Service      │────►│    Engine       │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Storage Layer                            │
│                                                                 │
│  ┌────────────────┐   ┌────────────────┐   ┌────────────────┐  │
│  │   PostgreSQL   │   │      Mem0      │   │    Graphiti    │  │
│  │ (UserProfile)  │   │    (Vector)    │   │ (Entities/Rels)│  │
│  └────────────────┘   └────────────────┘   └────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
         ▲                       ▲                       ▲
         │                       │                       │
┌─────────────────────────────────────────────────────────────────┐
│                Background Processing (Celery)                   │
└─────────────────────────────────────────────────────────────────┘
```

## Current Implementation Status

Based on the completed tasks in v1_tasks.md, we have:

1. ✅ Removed DAO-related models and components
2. ✅ Created UserProfile model and schema
3. ✅ Refined Graphiti schema
4. ✅ Implemented basic chat log ingestion
5. ✅ Implemented conversation management and summarization
6. ✅ Created initial entity extraction
7. ✅ Refactored extraction into `ExtractionPipeline` and `TraitExtractionService`
8. ✅ Fixed Graph API scope filtering issues

## Remaining Implementation Priorities

1. Complete conversation pruning/archiving (3.1.4)
2. Implement feedback mechanisms (3.1.7)
3. Develop comprehensive testing strategy (3.1.8)
4. Optimize performance for chat components (3.1.9)
5. Implement UserProfile fetcher node in LangGraph (4.2.1)
6. Develop the recommendation engine (4.3.x)
7. Add additional data sources (3.2.x, 3.3.x)

## Best Practices and Patterns to Follow

1. **Single Responsibility Principle**: Each component should have one reason to change
2. **Dependency Inversion**: Depend on abstractions, not concrete implementations
3. **Feature Flags**: Use feature flags for progressive rollout of new capabilities
4. **Idempotent Operations**: Ensure API operations can be safely retried
5. **Circuit Breakers**: Protect the system from cascading failures when external services fail
6. **Graceful Degradation**: System should continue to function (with reduced capabilities) when subsystems fail
7. **Observability**: Comprehensive logging, monitoring, and tracing

## Specific Architectural Guidance for Upcoming Tasks

### For UserProfile Integration (4.2.x)
- Implement a cache layer for UserProfile to reduce database load
- Use a publisher-subscriber pattern for profile updates
- Create clear validation rules for profile data

### For Recommendation Engine (4.3.x)
- Use a pipeline architecture with clear stages (context gathering, analysis, generation, scoring)
- Implement A/B testing capability from the start
- Use a configurable scoring system for ranking recommendations

### For Additional Data Sources (3.2.x, 3.3.x)
- Define a clear interface that all data source connectors must implement
- Use a registration system so new sources can be added without modifying core code
- Implement a consistent error handling and retry strategy

## Conclusion

This architecture builds on our existing implementation while providing clear guidance for remaining tasks. It emphasizes:

1. Separation of concerns through well-defined components
2. Extensibility through appropriate design patterns
3. Scalability through asynchronous processing
4. Resilience through proper error handling
5. Maintainability through consistent patterns

By following these architectural principles, we can complete the Digital Twin V1 with a robust, maintainable, and extensible system that meets our requirements while avoiding unnecessary refactoring of existing components. 