# Digital Twin V1 Migration Tasks

This document outlines the task breakdown for our migration from v0 (DAO multi-agent) to v1 (personal digital twin) architecture. Tasks are organized into phases with dependencies clearly marked.

## Migration Strategy Overview

We're pivoting from the DAO multi-agent approach to focus entirely on creating a faithful digital twin that can:

1. Understand user preferences, skills, interests, and relationships
2. Ingest multiple data sources to build a comprehensive user model
3. Generate personalized recommendations based on external context
4. Update its knowledge based on user feedback and interactions

The implementation is organized into 6 phases, with **phases 1-3 forming the critical path**. The tasks are numbered by:
- Phases (1-5) - High-level grouping by implementation timeline
- Task categories (1.x-6.x) - Functional groupings regardless of phase:
    - 1.x: Database Schema Changes
    - 2.x: Graphiti Schema
    - 3.x: Data Ingestion
    - 4.x: Agent Components
    - 5.x: API Endpoints
    - 6.x: Metrics

This approach allows tracking both when a task should be done (phase) and what functional area it belongs to (category number).

## Phase 1: Foundation

### 1. Database Schema Changes

**1.1. Remove DAO-related models**
- [x] Identify and delete `app/db/models/proposal.py` and `app/db/models/vote.py`
- [x] Remove model imports and references in other files
- [x] Test codebase compilation without these models

**1.2. Create UserProfile model**
- [x] Create new file `app/db/models/user_profile.py`
- [x] Define UserProfile class with these fields:
  - [x] `preferences`: JSON field for user preferences
  - [x] `interests`: JSON array of user interests
  - [x] `skills`: JSON array of user skills
  - [x] `dislikes`: JSON array of user dislikes
  - [x] `communication_style`: JSON object for communication preferences
  - [x] `key_relationships`: JSON array for important relationships
- [x] Add proper relationship to User model
- [x] Implement default values and type hints

**1.3. Update User model**
- [x] Add relationship to UserProfile in `app/db/models/user.py`
- [x] Ensure cascade delete for orphaned profiles
- [x] Update existing queries that work with User

**1.4. Create Alembic migration**
- [x] Generate migration: `alembic revision --autogenerate -m "remove dao models, add user profile"`
- [x] Review and adjust generated migration
- [x] Ensure proper upgrade and downgrade paths

**1.5. Test database migrations**
- [x] Define overall testing strategy (unit, integration, e2e) in a new file TESTING.md 
- [x] Setup necessary base test configurations/fixtures
- [x] Run upgrade migration on test database
- [x] Verify schema changes
- [x] Test downgrade path
- [x] Validate with actual data

*Dependencies: 1.4 depends on 1.1, 1.2, and 1.3; 1.5 depends on 1.4*

### 2. Graphiti Schema Refinements

**2.1. Remove DAO-related node types**
- [x] Remove Proposal, Vote, and PolicyTopic entities
- [x] Delete associated relationship definitions
- [x] Test schema validation without these components

**2.2. Define new node types**
- [x] Create Skill, Interest, Preference, Dislike, Person, TimeSlot nodes
- [x] Define properties for each node type
- [x] Create validation logic and test data

**2.3. Define new relationship types**
- [x] Define HAS_SKILL, INTERESTED_IN, PREFERS, DISLIKES, KNOWS, AVAILABILITY
- [x] Add properties like proficiency, strength, recurrence
- [x] Implement validation and test data

**2.4. Update document/event linking**
- [x] Ensure proper connections between nodes and User
- [x] Update existing queries
- [x] Test with sample data

**2.5. Create migration script**
- [x] Develop script to migrate existing Graphiti data
- [x] Handle DAO node/edge removal
- [x] Implement transformation logic
- [x] Add rollback capability

**2.6. Test Graphiti schema changes**
- [x] Run migration on test dataset
- [x] Verify structure and relationships
- [x] Test queries against new schema
- [x] Validate rollback procedure

*Dependencies: 2.3 depends on 2.2; 2.5 depends on 2.1, 2.2, 2.3, and 2.4; 2.6 depends on 2.5*

### 3. Basic Chat Log Ingestion

**3.1.1. Implement chat message persistence**
- [x] Create database models for `Conversation`, `ChatMessage`, and `MessageFeedback`
- [x] Implement necessary indexes for efficient querying 
- [x] Set up relationships between models and User
- [x] Create Alembic migration scripts
- [x] Implement conversation service for CRUD operations
- [x] Add transaction handling and robust error logging

**3.1.2. Create Mem0 ingestion pipeline**
- [x] Develop chat transformer for Mem0 to process raw messages
- [x] Implement tiered memory approach (recent messages vs summaries)
- [x] Add metadata tagging with source, confidence, and context
- [x] Create batch processing for efficient handling
- [x] Set up TTL policies for memory management
- [x] Implement error handling and retry mechanisms
- [x] Create API endpoints for chat so this can be tested with real data

**3.1.3. Extract entity information and update UserProfile**
- [x] Create Graphiti node/relationship creation service for chats (see `GraphitiService`) - make sure to dedupe
- [x] Implement LLM-based entity and trait extraction from chat logs if any (entity extraction already in `entity_extraction_gemini.py`, extend for traits)
- [x] Create mappers to UserProfile fields (preferences, interests, skills, etc)
- [x] Develop confidence scoring for extracted traits
- [x] Set thresholds for profile updates (e.g., minimum 0.6 confidence)
- [x] Implement conflict resolution for contradictory information (based on confidence)
- [x] Create direct UserProfile updates for high-confidence traits
- [x] Create simple page to view stored user knowledge (memories and graph data)
- [x] Add ability to delete an individual memory, or graphiti entity or relationship in the UX

**3.1.4. Implement session management**
- [x] Add button to conversation UI to trigger summarization of the conversation, implement conversation summarization 
- [x] Add automatic title generation for conversations
- [x] Create conversation boundary detection (for simplicity we can say this is when user creates a new conversation, or when we hit 20 new unsummarized messages in the conversation)
- [x] Store summaries in Posgres - only has one summary field for each conversation, which updates it each time with the new messages
- [x] Store memories in mem0 - these should be a new memory for each batch of new messages (we are storing them right now but not )
- [x] Make sure to track summarized messages, then we can dedupe and not re-summarize the already-summarized in Postgres and Mem0
- [x] remove twin/assistant messages from mem0 (we will just use summary memories)
- [x] remove twin/assistant messages from graphiti (no need for them)
- [x] Develop context preservation between sessions
- [ ] Create conversation pruning/archiving strategy
- [ ] Implement conversation status tracking (active, archived, deleted)
- [ ] Add metadata and context handling for conversations

**3.1.5. Set up background processing**
- [x] Configure Celery task queue for async processing
- [x] Implement periodic tasks for processing pending messages
- [x] Create scheduled tasks for conversation summarization
- [x] Add monitoring and task status reporting
- [x] Implement graceful failure handling

**3.1.6. Create comprehensive chat API endpoints**
- [x] Implement CRUD operations for conversations
  - [x] `GET /api/v1/chat/conversations` - list with pagination
  - [x] `GET /api/v1/chat/conversations/{id}` - conversation details with messages
  - [x] `POST /api/v1/chat` - create new conversation/message (combined endpoint)
  - [ ] `DELETE /api/v1/chat/conversations/{id}` - archive conversation (future)
- [x] Implement message management endpoints
  - [x] `GET /api/v1/chat/messages/{id}/mem0-status` - check message ingestion status
  - [x] Messages are created through the `/api/v1/chat` endpoint
  - [ ] `PUT /api/v1/chat/messages/{id}` - update message (future)
- [x] Create a simple chat UI for testing conversations
- [x] Add authentication checks (with fallback to mock user)
- [ ] Implement rate limiting and request validation
- [ ] Create documentation with Swagger/OpenAPI

**3.1.7. Implement feedback mechanisms**
- [ ] Create message feedback endpoints
  - [ ] `POST /api/v1/messages/{id}/feedback` - add feedback
  - [ ] `GET /api/v1/messages/{id}/feedback` - get feedback
- [ ] Implement feedback types (helpful, incorrect, insightful, etc.)
- [ ] Add feedback processing for profile improvement
- [ ] Create feedback analytics service
- [ ] Connect feedback with User Profile updates

**3.1.8. Develop testing strategy for chat components**
- [ ] Create unit tests for database models and constraints
- [ ] Implement service-level tests for conversation management
- [ ] Add integration tests for the full ingestion pipeline
- [ ] Create performance tests for high-volume scenarios
- [ ] Implement end-to-end tests for chat API

**3.1.9. Implement performance optimization**
- [ ] Add caching for frequent queries (Redis)
- [ ] Implement efficient pagination for large conversations
- [ ] Create database indexing strategy for chat queries
- [ ] Add query optimization for common patterns
- [ ] Implement conversation archiving for old/inactive conversations

*Dependencies: 3.1.2, 3.1.3, and 3.1.4 depend on 3.1.1; 3.1.5 depends on 3.1.2, 3.1.3, and 3.1.4; 3.1.6 depends on 3.1.1; 3.1.7 depends on 3.1.6; 3.1.8 depends on 3.1.6 and 3.1.7; 3.1.9 can be developed in parallel. All 3.1.x tasks depend on 1.x and 2.x; 3.1.3 specifically depends on UserProfile implementation (1.2)*

### 4. Remove DAO Components

**4.1. Remove DAO-related agent components**
- [x] Identify and remove DAO-related code
- [x] Update agent configurations
- [x] Remove DAO-specific prompts
- [x] Test agent functionality

**5.1. Remove DAO-related endpoints**
- [x] Remove `/proposals/*` endpoints
- [x] Update API documentation
- [x] Remove route handlers and services
- [x] Test API without these endpoints

*No dependencies - these can be done independently*

## Phase 2: Core Twin Functionality

### 4.2. Agent Profile Integration

**4.2.1. Create UserProfile fetcher node**
- [ ] Develop new LangGraph node
- [ ] Implement database integration
- [ ] Add caching for performance
- [ ] Create fallbacks for missing profiles

**4.2.2. Update context synthesis logic**
- [ ] Modify `merge_context` node to include profile
- [ ] Implement priority weighting
- [ ] Create hierarchical structure
- [ ] Develop profile incorporation templates

**4.2.3. Implement confidence and recency weighting**
- [ ] Add timestamp-based sorting
- [ ] Implement confidence calculation
- [ ] Create weighted merging algorithm
- [ ] Test with various scenarios

**4.2.4. Add attribution tracking**
- [ ] Create attribution metadata schema
- [ ] Implement source tracking
- [ ] Develop attribution in responses
- [ ] Test accuracy

*Dependencies: 4.2.x depends on database schema changes (1.x)*

### 5.2. User Profile Endpoints

**5.2.1. Create GET /api/v1/profile endpoint**
- [ ] Implement route handler
- [ ] Create profile service
- [ ] Add response serialization
- [ ] Implement error handling
- [ ] Frontend view to see the UserProfile
- [ ] Add api endpoint and button to clear out the UserProfile

**5.2.2. Implement PUT /api/v1/profile**
- [ ] Create route handler for updates
- [ ] Implement validation
- [ ] Create update service
- [ ] Add concurrency control

**5.2.3. Add validation logic**
- [ ] Implement schema validation
- [ ] Create business logic validators
- [ ] Add security protections
- [ ] Implement partial updates

**5.2.4. Create response formatting**
- [ ] Design response schema with stats
- [ ] Implement stat gathering
- [ ] Add pagination
- [ ] Create detailed/summary views

*Dependencies: 5.2.x depends on database schema changes (1.x)*

### 5.4. Enhanced Chat Endpoints

**5.4.1. Update POST /api/v1/chat**
- [x] Modify endpoint to create/use Conversation records if not already
- [x] Add conversation_id parameter (optional, creates new if absent)
- [ ] Implement context capture from request (project, task, etc.)
- [ ] Add support for streaming responses
- [ ] Ensure compatibility with existing clients

**5.4.2. Implement Mem0 feedback loop**
- [x] Create background task triggering for message ingestion
- [x] Ensure all messages are stored in Postgres before response
- [ ] Implement duplicate detection and deduplication logic
- [x] Add importance scoring for prioritization
- [x] Optimize TTL management based on message importance
- [ ] Create metadata enrichment from conversation context

**5.4.3. Integrate chat insights with background processing**
- [x] Connect chat processing pipeline to trait extraction (3.1.3)
- [ ] Implement message chunking and batching for efficient processing
- [ ] Create background task scheduling for non-blocking operation
- [ ] Set up retry logic and error handling for failed extractions
- [ ] Add monitoring and logging for extraction metrics

**5.4.4. Add conversational UX endpoints**
- [x] Create endpoints for conversation history retrieval
- [x] Implement conversation title management
- [x] Add message reaction/feedback support
- [x] Implement pagination and filtering
- [x] Create simple HTML/JS frontend for conversation interactions

**5.4.5. Implement real-time chat capability (this can wait)**
- [ ] Setup WebSocket server for bidirectional communication
- [ ] Create connection management for multiple concurrent users
- [ ] Implement authentication and session handling
- [ ] Add message protocol with typing indicators and read receipts
- [ ] Create client helpers for main app integration

*Dependencies: 5.4.x depends on chat ingestion (3.1.x)*

## Phase 3: Additional Data Sources

### 3.2. Calendar Integration

**3.2.1. Implement Google Calendar OAuth flow**
- [ ] Set up API credentials
- [ ] Create consent screen
- [ ] Implement authorization
- [ ] Create token handling
- [ ] Define error handling strategy for ingestion pipelines (e.g., retries, logging, DLQ).

**3.2.2. Create data fetcher for calendar events**
- [ ] Implement API client
- [ ] Create pagination handling
- [ ] Implement circuit breakers or robust error handling for external API calls
- [ ] Implement incremental sync

**3.2.3. Develop parser for calendar data**
- [ ] Create event parser
- [ ] Implement recurrence handling
- [ ] Add location extraction
- [ ] Create entity recognition

**3.2.4. Create Mem0 and Graphiti ingestion pipelines**
- [ ] Develop transformers if not already
- [ ] Implement event-to-memory conversion if not already
- [ ] Create relationship extraction if not already
- [ ] Add interest detection

*Dependencies: 3.2.x can be done after Phase 1*

### 3.3. Social Media Integration

**3.3.1. Fetch scraped data from Twitter**
- [ ] There is an api service at `https://twitter-scraper-finetune.onrender.com` that we can use, just need to send it the handle
- [ ] Poll the job at `https://twitter-scraper-finetune.onrender.com/twitter_scrape_jobs/{ID}/status` until it is done, then download the results (zip file of tweets in json)

**3.3.2. Develop tweet parser/analyzer**
- [ ] Create content extraction
- [ ] Implement sentiment analysis, update UserProfile
- [ ] Add topic classification, update UserProfile
- [ ] Create entity and relationships extraction, update Graphiti
- [ ] Create trait extraction, update Graphiti, mem0, UserProfile

*Dependencies: 3.3.x can be done after Phase 1*

### 4.5. Trait Extraction Agent

**4.5.1. Develop comprehensive trait extraction system**
- [ ] Build upon the chat-specific extraction (3.1.3)
- [ ] Extend extraction to handle ingested docs, updating UserProfile
- [ ] Extend extraction to handle our other data sources (chat, calendar, social media etc), updating UserProfile
- [ ] Create unified processing workflow across sources
- [ ] Implement source-specific extractors with consistent output format
- [ ] Develop advanced prompt templates with source-specific considerations

**4.5.2. Implement advanced confidence scoring**
- [ ] Design multi-source confidence calculation algorithm
- [ ] Create validation rules for cross-referencing traits
- [ ] Implement confidence boosting for traits confirmed across sources
- [ ] Add decay functions for older/stale trait evidence
- [ ] Set dynamic thresholds based on trait category and evidence quality

**4.5.3. Create enhanced UserProfile update logic**
- [ ] Implement comprehensive update service for multi-source traits
- [ ] Create sophisticated merge strategies for conflicting traits
- [ ] Add conflict resolution with source prioritization
- [ ] Implement batch processing for efficient updates
- [ ] Add versioning to track trait evolution over time

**4.5.4. Add Graphiti relationship creation**
- [ ] Develop trait-to-graph mapping
- [ ] Implement batch creation of relationships
- [ ] Add validation against existing graph structure
- [ ] Create cleanup procedures for obsolete relationships
- [ ] Implement confidence-weighted relationships

*Dependencies: 4.5.x builds upon the basic trait extraction in 3.1.3 and can be developed in parallel with 4.2.x, but full integration depends on 4.2.x*

## Phase 4: Recommendation System

### 4.3. Recommendation Engine

**4.3.1. Create dedicated recommendation node**
- [ ] Develop new LangGraph node
- [ ] Implement configuration options
- [ ] Create I/O schema
- [ ] Add logging

**4.3.2. Implement external context analysis**
- [ ] Create parsing logic
- [ ] Implement keyword extraction
- [ ] Develop context categorization
- [ ] Add relevance scoring

**4.3.3. Develop personalized recommendation generation**
- [ ] Create prompt templates
- [ ] Implement profile-aware logic
- [ ] Add recommendation diversity
- [ ] Create the fallback loop:
    - [ ] Implement logic for the agent to detect insufficient information and generate targeted clarification questions for the user.
    - [ ] Design the agent flow to process user answers to clarification questions. The flow looks like "insufficient info -> ask clarifying question -> process answer -> end when all info collected -> generate recommendation".

**4.3.4. Add justification and confidence scoring**
- [ ] Implement reasoning generation
- [ ] Create confidence calculation
- [ ] Add source attribution
- [ ] Develop presentation formatting

*Dependencies: 4.3.x depends on agent profile integration (4.2.x)*

### 4.4. Feedback Mechanisms

**4.4.1. Create feedback collection workflow**
- [ ] Design feedback schema
- [ ] Implement UI hooks
- [ ] Create API endpoints
- [ ] Add validation

**4.4.2. Develop UserProfile update logic**
- [ ] Create update service based on feedback
- [ ] Implement preference adjustments
- [ ] Add preference discovery
- [ ] Create feedback-to-profile mapping

**4.4.3. Implement conflict resolution**
- [ ] Design conflict detection
- [ ] Create resolution strategies
- [ ] Implement attribute versioning
- [ ] Add notifications

**4.4.4. Add temporal weighting**
- [ ] Implement time decay functions
- [ ] Create recency boost
- [ ] Develop preference history tracking
- [ ] Add visualization

*Dependencies: 4.4.x depends on recommendation engine (4.3.x)*

### 5.3. Recommendation Endpoints

**5.3.1. Create POST /api/v1/recommendations endpoint**
- [ ] Implement route handler
- [ ] Create schema and validation
- [ ] Add rate limiting
- [ ] Implement error handling

**5.3.2. Implement request validation**
- [ ] Create validation schema
- [ ] Implement validation logic
- [ ] Add input sanitization
- [ ] Create error messages

**5.3.3. Connect to agent recommendation workflow**
- [ ] Integrate with LangGraph
- [ ] Implement async processing
- [ ] Add timeout handling
- [ ] Create status checking

**5.3.4. Format responses**
- [ ] Design response schema
- [ ] Implement serialization
- [ ] Add pagination
- [ ] Create multiple formats

*Dependencies: 5.3.x depends on recommendation engine (4.3.x)*

## Phase 5: Metrics & Evaluation

### 6.1. Trait Recall Accuracy

**6.1.1. Create a golden dataset**
- [ ] Identify key traits
- [ ] Create test cases
- [ ] Implement query variations
- [ ] Develop scoring criteria

**6.1.2. Develop a test harness**
- [ ] Create testing framework
- [ ] Implement query generation
- [ ] Add result evaluation
- [ ] Create reporting

**6.1.3. Implement accuracy scoring**
- [ ] Design scoring algorithm
- [ ] Create partial matching
- [ ] Implement adjusted scoring
- [ ] Add category metrics

**6.1.4. Create reporting dashboard**
- [ ] Design visualization
- [ ] Implement trend analysis
- [ ] Add drill-down
- [ ] Create exports

*Dependencies: 6.1.x depends on UserProfile implementation (1.2, 1.3)*

### 6.2. Recommendation Relevance Scoring

**6.2.1. Design user feedback collection**
- [ ] Create UI components
- [ ] Implement feedback types
- [ ] Add implicit tracking
- [ ] Develop A/B testing

**6.2.2. Implement relevance scoring algorithm**
- [ ] Design multi-dimensional scoring
- [ ] Create normalization
- [ ] Implement comparison
- [ ] Add confidence intervals

**6.2.3. Create historical tracking**
- [ ] Implement time-series storage
- [ ] Create aggregation
- [ ] Develop anomaly detection
- [ ] Add goal tracking

**6.2.4. Add visualization**
- [ ] Design dashboards
- [ ] Implement trend views
- [ ] Create quality comparison
- [ ] Add segment analysis

*Dependencies: 6.2.x depends on recommendation engine (4.3.x) and feedback mechanism (4.4.x)*

### 6.3. Source Diversity Metrics

**6.3.1. Create source tracking**
- [ ] Implement source metadata
- [ ] Create usage tracking
- [ ] Add attribution logging
- [ ] Develop categorization

**6.3.2. Develop diversity measurement**
- [ ] Design diversity metrics
- [ ] Implement balance calculation
- [ ] Create time-window analysis
- [ ] Add user-specific metrics

**6.3.3. Implement gap analysis**
- [ ] Create domain coverage mapping
- [ ] Implement source mapping
- [ ] Develop detection
- [ ] Add recommendations

**6.3.4. Build reporting interface**
- [ ] Design dashboard
- [ ] Implement visualization
- [ ] Create alerts
- [ ] Add improvement suggestions

*Dependencies: 6.3.x depends on data source implementations (3.x)*

### 6.4. Knowledge Gap Identification

**6.4.1. Implement topic coverage analysis**
- [ ] Create topic modeling
- [ ] Implement completeness scoring
- [ ] Add confidence assessment
- [ ] Develop temporal analysis

**6.4.2. Develop confidence scoring**
- [ ] Design domain metrics
- [ ] Implement uncertainty quantification
- [ ] Create confidence visualization
- [ ] Add trend analysis

**6.4.3. Create prompts for targeted questions**
- [ ] Design question templates
- [ ] Implement prioritization
- [ ] Add conversational strategies
- [ ] Create feedback loop

**6.4.4. Build UI for knowledge gaps**
- [ ] Design interface
- [ ] Implement gap filling
- [ ] Create gamification
- [ ] Add progress tracking

*Dependencies: 6.4.x depends on 6.1.x, 6.2.x, and 6.3.x*

## Critical Path Summary

The critical path for this migration is:

1. **Database Schema Changes** (1.x) → 
2. **Agent Profile Integration** (4.2.x) → 
3. **Recommendation Engine** (4.3.x) → 
4. **Feedback Mechanisms** (4.4.x) → 
5. **Recommendation Endpoints** (5.3.x) → 
6. **Recommendation Metrics** (6.2.x)

This path ensures we build the most essential functionality first (personalized recommendations) while allowing for parallel work on non-blocking tasks like additional data sources and advanced features. 